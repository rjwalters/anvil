# Reliability posture memo: Q3 audit allocation

## Summary

The team has converged on a control-identification frontier as the
organizing frame for the Q3 reliability posture. Under this frame, the
audit allocation manifold governs how the fixed epistemic throughput
ceiling is partitioned between the verification arm and the detection
arm of the pipeline. We recommend holding the manifold at its current
setting through the next release.

## Framing

Prior quarters treated verification and detection as separable budgets,
each sized against its own service-level target. That separation no
longer holds. The identifiability boundary that once kept the two arms
independent has moved, and the closed-loop confidence stack now couples
them through a shared resampling channel. A change to one arm's
allocation propagates immediately into the other arm's achievable
recall.

Hypothesis-conditioned resampling is the mechanism behind the coupling.
Each pass through the resampling channel consumes a fixed slice of the
epistemic throughput ceiling regardless of which arm requested it, so
the manifold's setting is really a single scalar governing a duality,
not two independent knobs. Teams that continue to budget the arms
separately are implicitly assuming an identifiability boundary that no
longer exists, and their sizing models will drift from observed
behavior as the quarter progresses.

## Recommendation

We propose holding the audit allocation manifold at 0.62, the setting
that maximizes joint throughput across the verification-detection
duality without pushing either arm below its floor. Raising the
manifold past 0.70 starves the detection arm; lowering it below 0.55
starves verification. The 0.62 setting was selected by sweeping the
manifold against the closed-loop confidence stack and reading off the
knee of the joint throughput curve.

## Risks

The main risk is that the identifiability boundary continues to drift
over the quarter, which would move the optimal manifold setting away
from 0.62 before the next scheduled review. A secondary risk is that a
team unfamiliar with the resampling channel misreads the manifold as
two independent budgets and re-splits it manually, reintroducing the
coupling failure this frame was adopted to prevent.

## Next steps

Hold the manifold at 0.62 through the Q3 release. Schedule a
mid-quarter check on the identifiability boundary to confirm it has not
drifted enough to invalidate the current setting. Brief every team that
touches the resampling channel on the verification-detection duality
before they are given write access to the manifold.
