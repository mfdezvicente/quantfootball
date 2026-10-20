"""Regularized goal-count research: Poisson, NB2 and shared Gamma-Poisson pace.

The shared-pace law integrates one Gamma(k,k) multiplier per match. Conditional
goals are independent Poisson; marginal variances exceed means and covariance is
positive. This is not an implementation of bivariate-Poisson or Sarmanov models.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import digamma, gammaln
from scipy.stats import binom, nbinom, poisson, skellam

FAMILIES = ('poisson', 'independent_nb', 'shared_tempo')


def likelihood(eta_h, eta_a, x, y, log_k, family):
    """Return log probability and analytic derivatives wrt log means/log shape."""
    h, a = np.exp(eta_h), np.exp(eta_a)
    if family == 'poisson':
        return x*eta_h-h-gammaln(x+1)+y*eta_a-a-gammaln(y+1), x-h, y-a, np.zeros_like(h)
    k = np.exp(log_k)
    if family == 'independent_nb':
        def side(mu, eta, z):
            logp = gammaln(z+k)-gammaln(k)-gammaln(z+1)+k*np.log(k)+z*eta-(z+k)*np.log(k+mu)
            deta = k*(z-mu)/(k+mu)
            dk = digamma(z+k)-digamma(k)+np.log(k)+1-np.log(k+mu)-(z+k)/(k+mu)
            return logp, deta, dk*k
        ph, dh, kh = side(h, eta_h, x)
        pa, da, ka = side(a, eta_a, y)
        return ph+pa, dh, da, kh+ka
    if family != 'shared_tempo':
        raise ValueError('Unknown goal family.')
    total, denominator = x+y, k+h+a
    logp = (gammaln(total+k)-gammaln(k)-gammaln(x+1)-gammaln(y+1)
            + k*np.log(k)+x*eta_h+y*eta_a-(total+k)*np.log(denominator))
    dk = digamma(total+k)-digamma(k)+np.log(k)+1-np.log(denominator)-(total+k)/denominator
    return logp, x-(total+k)*h/denominator, y-(total+k)*a/denominator, k*dk


@dataclass
class FlexibleGoalModel:
    family: str = 'independent_nb'
    half_life_days: float = 365
    ridge: float = 10
    lookback_days: int = 1461
    dispersion_precision: float = 50
    teams: dict = field(default_factory=dict, init=False)
    parameters: np.ndarray | None = field(default=None, init=False)
    diagnostics: dict = field(default_factory=dict, init=False)

    def fit(self, matches, cutoff):
        if self.family not in FAMILIES:
            raise ValueError('Unknown goal family.')
        if not np.isfinite([self.half_life_days,self.ridge,self.dispersion_precision]).all() or min(self.half_life_days,self.ridge,self.dispersion_precision) <= 0:
            raise ValueError('Positive finite prior settings required.')
        boundary = pd.Timestamp(cutoff)
        if pd.isna(boundary) or boundary.tz is not None or boundary != boundary.normalize():
            raise ValueError('Use a calendar cutoff.')
        data = matches.copy()
        data['date'] = pd.to_datetime(data.date)
        data = data[(data.date < boundary) & (data.date >= boundary-pd.Timedelta(days=self.lookback_days))].copy()
        if data.empty or data.date.isna().any() or data.competition_code.nunique() != 1:
            raise ValueError('One competition with prior results required.')
        if data.duplicated(['date','home_team','away_team']).any() or data.home_team.eq(data.away_team).any():
            raise ValueError('Duplicate or self-playing fixtures.')
        goals = data[['home_goals','away_goals']].to_numpy(dtype=float)
        if not np.isfinite(goals).all() or (goals < 0).any() or (goals != np.floor(goals)).any():
            raise ValueError('Nonnegative integer goals required.')
        names = sorted(set(data.home_team) | set(data.away_team))
        teams = {name:i for i,name in enumerate(names)}
        n = len(teams)
        home, away = data.home_team.map(teams).to_numpy(), data.away_team.map(teams).to_numpy()
        x,y = goals.T
        weights = np.exp2(-(boundary-data.date).dt.days.to_numpy()/self.half_life_days)
        def objective(theta):
            h = theta[0]+theta[1]+theta[2:2+n][home]+theta[2+n:2+2*n][away]
            a = theta[0]+theta[2:2+n][away]+theta[2+n:2+2*n][home]
            logk = theta[-1] if self.family != 'poisson' else np.log(1000)
            logp,dh,da,dk = likelihood(h,a,x,y,logk,self.family)
            eh,ea = -weights*dh,-weights*da
            gradient = np.r_[np.sum(eh+ea),np.sum(eh),
                np.bincount(home,eh,minlength=n)+np.bincount(away,ea,minlength=n),
                np.bincount(away,eh,minlength=n)+np.bincount(home,ea,minlength=n)]
            loss = -np.sum(weights*logp)+self.ridge*np.sum(theta[2:2+2*n]**2)/2
            gradient[2:] += self.ridge*theta[2:2+2*n]
            if self.family != 'poisson':
                # Shrink overdispersion alpha=1/k towards zero, not towards a
                # fitted historical optimum. Bounds allow near-Poisson behavior.
                penalty = self.dispersion_precision*np.exp(-2*logk)/2
                loss += penalty
                gradient = np.r_[gradient,-np.sum(weights*dk)-2*penalty]
            return float(loss),gradient
        initial = np.zeros(2+2*n+(self.family != 'poisson'))
        initial[0] = np.log(max(np.average(y,weights=weights),.1))
        initial[1] = np.log(max(np.average(x,weights=weights),.1))-initial[0]
        if self.family != 'poisson':
            initial[-1] = np.log(20)
        bounds = [(-2,2),(-1,1)]+[(-2,2)]*(2*n)
        if self.family != 'poisson':
            bounds += [(np.log(.5),np.log(1000))]
        fitted = minimize(objective,initial,jac=True,method='L-BFGS-B',bounds=bounds,
                          options={'maxiter':800,'ftol':1e-10,'gtol':1e-5})
        if not fitted.success or not np.isfinite(fitted.x).all():
            raise RuntimeError(f'Flexible goal fit failed: {fitted.message}')
        self.teams,self.parameters = teams,fitted.x
        shape = None if self.family == 'poisson' else float(np.exp(fitted.x[-1]))
        self.diagnostics = {'family':self.family,'cutoff':boundary.isoformat(),
            'training_last_date':data.date.max().isoformat(),'training_matches':len(data),
            'converged':bool(fitted.success),'iterations':int(fitted.nit),'shape_k':shape,
            'dispersion_at_bound':shape is not None and (shape < .5001 or shape > 999),
            'objective':float(fitted.fun),'half_life_days':self.half_life_days,'ridge':self.ridge,
            'dispersion_precision':self.dispersion_precision,'lookback_days':self.lookback_days}
        return self

    def expected_goals(self, home, away, *, allow_unknown=False):
        if self.parameters is None or home == away:
            raise ValueError('Fit model and use different teams.')
        if not allow_unknown and (home not in self.teams or away not in self.teams):
            raise ValueError('Unknown team.')
        n = len(self.teams)
        def strengths(team):
            i = self.teams.get(team)
            return (0.,0.) if i is None else (self.parameters[2+i],self.parameters[2+n+i])
        ah,dh = strengths(home)
        aa,da = strengths(away)
        return float(np.exp(self.parameters[0]+self.parameters[1]+ah+da)),float(np.exp(self.parameters[0]+aa+dh))

    def _shape(self):
        return float(np.exp(self.parameters[-1]))

    def predict_proba(self,home,away,*,allow_unknown=False):
        h,a = self.expected_goals(home,away,allow_unknown=allow_unknown)
        return count_probabilities(h,a,self.family,None if self.family == 'poisson' else self._shape())

    def predict_pleno(self,home,away,*,allow_unknown=False):
        h,a = self.expected_goals(home,away,allow_unknown=allow_unknown)
        return pleno_probabilities(h,a,self.family,None if self.family == 'poisson' else self._shape())


def count_probabilities(h,a,family,k=None,tail=1e-12):
    if not np.isfinite([h,a]).all() or min(h,a) <= 0 or family not in FAMILIES:
        raise ValueError('Positive means and supported family required.')
    if family == 'poisson':
        p = np.array([skellam.sf(0,h,a),skellam.pmf(0,h,a),skellam.cdf(-1,h,a)])
    else:
        if k is None or not np.isfinite(k) or k <= 0:
            raise ValueError('Positive shape required.')
        if family == 'shared_tempo':
            probability = k/(k+h+a)
            limit = int(nbinom.isf(tail,k,probability))
            if limit > 100000:
                raise ValueError('Tail support exceeds safe research range.')
            n = np.arange(limit+1)
            mass = nbinom.pmf(n,k,probability)
            home = float(np.sum(mass*binom.sf(n//2,n,h/(h+a))))
            draw = float(np.sum(mass[n%2 == 0]*binom.pmf(n[n%2 == 0]//2,n[n%2 == 0],h/(h+a))))
            away = float(np.sum(mass*binom.cdf((n-1)//2,n,h/(h+a))))
        else:
            lh,la = [int(nbinom.isf(tail,k,k/(k+mu))) for mu in (h,a)]
            if max(lh,la) > 100000:
                raise ValueError('Tail support exceeds safe research range.')
            x,y = np.arange(lh+1),np.arange(la+1)
            ph,pa = nbinom.pmf(x,k,k/(k+h)),nbinom.pmf(y,k,k/(k+a))
            home = float(np.sum(ph*nbinom.cdf(x-1,k,k/(k+a))))
            away = float(np.sum(pa*nbinom.cdf(y-1,k,k/(k+h))))
            diagonal = np.arange(min(lh,la)+1)
            draw = float(np.sum(nbinom.pmf(diagonal,k,k/(k+h))*nbinom.pmf(diagonal,k,k/(k+a))))
        p = np.array([home,draw,away])
    if not np.isfinite(p).all() or (p < 0).any() or abs(p.sum()-1) > 1e-9:
        raise ArithmeticError('Lost goal probability mass.')
    return dict(zip(('H','D','A'),(p/p.sum()).tolist()))


def pleno_probabilities(h,a,family,k=None):
    # Reuse validation before evaluating exact 0/1/2/3+ marginals.
    count_probabilities(h,a,family,k)
    small = np.arange(3)
    ph = poisson.pmf(small,h) if family == 'poisson' else nbinom.pmf(small,k,k/(k+h))
    pa = poisson.pmf(small,a) if family == 'poisson' else nbinom.pmf(small,k,k/(k+a))
    if family == 'shared_tempo':
        x,y = np.meshgrid(small,small,indexing='ij')
        joint = np.exp(likelihood(np.log(h),np.log(a),x,y,np.log(k),family)[0])
    else:
        joint = np.outer(ph,pa)
    grid = np.zeros((4,4))
    grid[:3,:3] = joint
    grid[:3,3],grid[3,:3] = ph-joint.sum(axis=1),pa-joint.sum(axis=0)
    grid[3,3] = 1-grid.sum()
    if grid.min() < -1e-10 or not np.isfinite(grid).all():
        raise ArithmeticError('Invalid Pleno mass.')
    grid = np.maximum(grid,0)
    labels = ('0','1','2','M')
    return {f'{u}-{v}':float(grid[i,j]) for i,u in enumerate(labels) for j,v in enumerate(labels)}
