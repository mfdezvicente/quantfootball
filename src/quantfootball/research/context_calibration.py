"""Low-dimensional context calibration shrunk towards the supplied probabilities."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax

from quantfootball.research.diagnostics import PROBS, validate


def context_design(frame):
    p = frame[PROBS].to_numpy()
    if (not len(p) or not np.isfinite(p).all() or (p <= 0).any()
            or not np.allclose(p.sum(axis=1),1,atol=1e-8)):
        raise ValueError('Positive normalized probabilities required.')
    goals = frame['expected_total_goals'].to_numpy(dtype=float)
    if not np.isfinite(goals).all() or (goals <= 0).any():
        raise ValueError('Positive prior expected total goals required.')
    return np.column_stack([np.ones(len(p)),.2-(p[:,0]-p[:,2])**2,
                            np.clip(np.log(goals/2.5),-1.5,1.5),16*(p[:,1]-.25)**2])


def apply_context(frame, config):
    x = context_design(frame)
    theta = np.asarray(config['parameters'],dtype=float)
    if theta.shape != (6,) or not np.isfinite(theta).all():
        raise ValueError('Invalid context calibration parameters.')
    logits = np.exp(theta[0])*np.log(frame[PROBS].to_numpy())
    logits[:,0] += theta[1]
    logits[:,2] -= theta[1]
    logits[:,1] += x@theta[2:]
    return softmax(logits,axis=1)


def fit_context(frame,cutoff,precision=100):
    boundary = pd.Timestamp(cutoff)
    if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
        raise ValueError('Calendar calibration cutoff required.')
    if not np.isfinite(precision) or precision <= 0:
        raise ValueError('Positive prior precision required.')
    dates,cuts = pd.to_datetime(frame.date),pd.to_datetime(frame.cutoff)
    if dates.isna().any() or cuts.isna().any() or (dates < cuts).any():
        raise ValueError('Prediction cannot occur after its fixture date.')
    train = frame[pd.to_datetime(frame.date) < boundary].copy()
    validate(train)
    if len(train) < 100:
        raise ValueError('At least one hundred prior labelled forecasts required.')
    x = context_design(train)
    logits = np.log(train[PROBS].to_numpy())
    y = np.array([('H','D','A').index(r) for r in train.result])
    target = np.eye(3)[y]
    def objective(theta):
        z = np.exp(theta[0])*logits
        z[:,0] += theta[1]
        z[:,2] -= theta[1]
        z[:,1] += x@theta[2:]
        p = softmax(z,axis=1)
        residual = p-target
        loss = -np.log(p[np.arange(len(p)),y]).sum()+precision*np.sum(theta**2)/2
        grad = np.r_[np.sum(residual*logits)*np.exp(theta[0]),
                     np.sum(residual[:,0]-residual[:,2]),x.T@residual[:,1]]+precision*theta
        return float(loss),grad
    fit = minimize(objective,np.zeros(6),jac=True,method='L-BFGS-B',
                   bounds=[(np.log(.67),np.log(1.5)),(-.3,.3)]+[(-.5,.5)]*4)
    if not fit.success or not np.isfinite(fit.x).all():
        raise RuntimeError(f'Context calibration failed: {fit.message}')
    return {'mode':'context','parameters':fit.x.tolist(),'precision':precision,
            'selected_before':boundary.isoformat(),'training_last_date':pd.to_datetime(train.date).max().isoformat(),
            'fit_matches':len(train),'converged':bool(fit.success),
            'inputs':'Own probability balance, squared draw deviation and prior Poisson total-goal estimate.'}
