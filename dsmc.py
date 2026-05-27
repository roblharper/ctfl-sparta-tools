from flow import Flow


class DSMC:
    def __init__(self, flow: Flow, dt: float):
        self.flow = flow
        self.dt = dt

    def collisions_per_timestep(self) -> float:
        """Expected number of collisions per particle per timestep.

        Derived directly from the mean collision time of the flow:

            N_coll = Δt / τ_coll

        A value well below 1 is required for DSMC validity — the timestep
        must be a fraction of the mean collision time so that each simulated
        collision event represents a statistically meaningful sample.

        Returns
        -------
        float
            Dimensionless collisions per particle per timestep.
        """
        return self.dt / self.flow.mean_collision_time()
