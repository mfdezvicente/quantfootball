import numpy as np
import pandas as pd
import pytest
from scipy.integrate import quad
from scipy.stats import gamma, poisson

from quantfootball.models.dixon_coles import DixonColesModel
from quantfootball.research.context_calibration import apply_context, fit_context
from quantfootball.research.flexible_goals import (
    FAMILIES,
    FlexibleGoalModel,
    count_probabilities,
    likelihood,
    pleno_probabilities,
)


@pytest.mark.parametrize('family',FAMILIES[:3])
def test_score_outcomes_match_brute_force_and_keep_full_pleno_tail(family):
    h,a,k = 1.7,.9,4.
    x,y = np.meshgrid(np.arange(80),np.arange(80),indexing='ij')
    grid = np.exp(likelihood(np.log(h),np.log(a),x,y,np.log(k),family)[0])
    expected = [grid[x>y].sum(),grid[x==y].sum(),grid[x<y].sum()]
    actual = count_probabilities(h,a,family,k)
    np.testing.assert_allclose(list(actual.values()),expected,atol=3e-10,rtol=0)
    pleno = pleno_probabilities(h,a,family,k)
    assert sum(pleno.values()) == pytest.approx(1,abs=1e-12)
    assert all(v >= 0 for v in pleno.values())
    assert pleno['M-M'] == pytest.approx(grid[(x>=3)&(y>=3)].sum(),abs=3e-10)


def test_shared_gamma_law_agrees_with_independent_numerical_integration():
    h,a,k,x,y = 1.7,.9,4.,2,1
    integrated = quad(lambda z:poisson.pmf(x,z*h)*poisson.pmf(y,z*a)*gamma.pdf(z,k,scale=1/k),0,np.inf)[0]
    actual = np.exp(likelihood(np.log(h),np.log(a),np.array([x]),np.array([y]),np.log(k),'shared_tempo')[0][0])
    assert actual == pytest.approx(integrated,rel=1e-8)


@pytest.mark.parametrize('family',FAMILIES[:3])
def test_analytic_likelihood_gradients_against_numerical_difference(family):
    from scipy.optimize import approx_fprime
    x,y = np.array([0.,2.,5.]),np.array([1.,3.,0.])
    theta = np.log([1.7,.9,4.])
    _,dh,da,dk = likelihood(theta[0],theta[1],x,y,theta[2],family)
    gradient = approx_fprime(theta,lambda v:float(likelihood(v[0],v[1],x,y,v[2],family)[0].sum()),1e-6)
    np.testing.assert_allclose(gradient,[dh.sum(),da.sum(),dk.sum()],atol=2e-5,rtol=0)


def history():
    rng = np.random.default_rng(43)
    rows = []
    for i in range(180):
        h,a = rng.poisson(1.5),rng.poisson(1.1)
        rows.append({'date':pd.Timestamp('2020-01-01')+pd.Timedelta(days=i),
            'home_team':['A','B','C','D'][i%4],'away_team':['A','B','C','D'][(i+1)%4],
            'competition_code':'es.1','home_goals':int(h),'away_goals':int(a),
            'result':'H' if h>a else 'D' if h==a else 'A'})
    return pd.DataFrame(rows)


def test_poisson_control_reproduces_existing_uncorrected_goal_model():
    data = history()
    control = FlexibleGoalModel(family='poisson').fit(data,'2020-07-01')
    old = DixonColesModel(ridge=10).fit(data,'2020-07-01')
    np.testing.assert_allclose(list(control.predict_proba('A','B').values()),
        list(old.predict_proba('A','B',correction=False).values()),atol=3e-5,rtol=0)


@pytest.mark.parametrize('family',FAMILIES)
def test_goal_fit_ignores_future_labels_and_rejects_unknown_teams(family):
    data = history()
    cutoff = '2020-05-01'
    before = FlexibleGoalModel(family=family).fit(data,cutoff)
    data.loc[data.date >= cutoff,['home_goals','away_goals']] = [9,0]
    after = FlexibleGoalModel(family=family).fit(data,cutoff)
    np.testing.assert_allclose(before.parameters,after.parameters,atol=1e-10)
    assert pd.Timestamp(before.diagnostics['training_last_date']) < pd.Timestamp(cutoff)
    with pytest.raises(ValueError):
        before.predict_proba('unknown','A')
    assert sum(before.predict_proba('unknown','A',allow_unknown=True).values()) == pytest.approx(1)


def forecast_frame():
    rng = np.random.default_rng(5)
    p = rng.dirichlet([3,2,2],160)
    dates = pd.date_range('2022-01-01',periods=len(p))
    return pd.DataFrame({'match_id':[str(i) for i in range(len(p))],
        'date':dates,'cutoff':dates-pd.to_timedelta(dates.dayofweek,unit='D'),
        'result':rng.choice(['H','D','A'],len(p)), 'expected_total_goals':2.5,
        'p_home':p[:,0],'p_draw':p[:,1],'p_away':p[:,2]})


def test_context_fit_ignores_future_labels_and_can_predict_unlabelled_matches():
    frame = forecast_frame()
    a = fit_context(frame,'2022-05-01')
    frame.loc[frame.date >= '2022-05-01','result'] = 'A'
    b = fit_context(frame,'2022-05-01')
    np.testing.assert_allclose(a['parameters'],b['parameters'],atol=1e-10)
    predicted = apply_context(frame.drop(columns=['result']),a)
    assert np.isfinite(predicted).all() and (predicted > 0).all()
    np.testing.assert_allclose(predicted.sum(axis=1),1)


def test_context_identity_and_bad_goal_context():
    frame = forecast_frame()
    np.testing.assert_allclose(apply_context(frame,{'parameters':[0]*6}),frame[['p_home','p_draw','p_away']])
    frame.loc[0,'expected_total_goals'] = np.nan
    with pytest.raises(ValueError):
        apply_context(frame,{'parameters':[0]*6})


@pytest.mark.parametrize('kappa',[-.95,0,.95])
def test_nb_low_score_kernel_keeps_marginals_and_positive_probability(kappa):
    from scipy.stats import nbinom

    from quantfootball.research.flexible_goals import low_score_shift
    h,a,k = 1.7,.9,4.
    x,y = np.meshgrid(np.arange(80),np.arange(80),indexing='ij')
    ph,pa = nbinom.pmf(x,k,k/(k+h)),nbinom.pmf(y,k,k/(k+a))
    grid = ph*pa
    marginal_h,marginal_a = grid.sum(axis=1),grid.sum(axis=0)
    shift = low_score_shift(h,a,k,kappa)
    grid[:2,:2] += [[shift,-shift],[-shift,shift]]
    assert grid.min() >= 0
    np.testing.assert_allclose(grid.sum(axis=1),marginal_h,atol=1e-12)
    np.testing.assert_allclose(grid.sum(axis=0),marginal_a,atol=1e-12)
    result = count_probabilities(h,a,'independent_nb_low',k,kappa=kappa)
    np.testing.assert_allclose(list(result.values()),[grid[x>y].sum(),grid[x==y].sum(),grid[x<y].sum()],atol=3e-10)
    pleno = pleno_probabilities(h,a,'independent_nb_low',k,kappa=kappa)
    assert sum(pleno.values()) == pytest.approx(1,abs=1e-12)
