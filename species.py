from dataclasses import dataclass, asdict
from typing import Dict
import json


@dataclass
class Species:
    id: str
    molwt: float = 0.0
    molmass: float = 0.0
    rotdof: float = 0.0
    rotrel: float = 0.0
    rottemp: float = 0.0
    vibdof: float = 0.0
    vibrel: float = 0.0
    vibtemp: float = 0.0
    specieswt: float = 1.0
    charge: float = 0.0
    diameter: float = 0.0
    omega: float = 0.0
    tref: float = 273.15
    alpha: float = 0.0
    rotc1: float = 0.0
    rotc2: float = 0.0
    birdc1: float = 0.0
    birdc2: float = 0.0
    MWA: float = 0.0
    MWB: float = 0.0
    mol_frac: float = 0.0
    homonuclear: bool = False

    @classmethod
    def load_all(cls, filename: str) -> Dict[str, "Species"]:
        with open(filename) as f:
            raw_data = json.load(f)
        return {species_id: cls(**data) for species_id, data in raw_data.items()}

    @staticmethod
    def save_all(species_dict: Dict[str, "Species"], filename: str):
        data = {species_id: asdict(species) for species_id, species in species_dict.items()}
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    @property
    def gamma(self) -> float:
        # Assumes fully-excited internal modes (classical equipartition).
        # At low T, vibrational modes are not fully excited — gamma may be overestimated.
        f = 3 + self.rotdof + self.vibdof
        return (f + 2) / f
