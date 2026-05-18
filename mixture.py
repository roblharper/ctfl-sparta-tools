from pathlib import Path
from species import Species
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        raise ImportError("TOML support requires Python >= 3.11 or 'pip install tomli'")

_DEFAULT_SPECIES_FILE = Path(__file__).parent / "species.json"


class Mixture:
    def __init__(self, species_dict: dict, name: str = None, species_file: Path = None):
        self.name = name
        species_path = species_file or _DEFAULT_SPECIES_FILE
        self.all_species = Species.load_all(str(species_path))
        self.species_dict = species_dict
        self.species = self._build()
        self.species_ids = list(self.species.keys())
        self.validate()

    def validate(self):
        total = sum(self.species_dict.values())
        if abs(total - 1) > 1e-2:
            raise ValueError(f"Mol fractions do not sum to 1. Total: {total}")

    def save(self, filename: str):
        lines = [f'name = "{self.name}"\n', '\n', '[species]\n']
        for sp_id, sp in self.species.items():
            lines.append(f'{sp_id} = {sp.mol_frac}\n')
        with open(filename, 'w') as f:
            f.writelines(lines)

    @classmethod
    def load(cls, filename: str) -> "Mixture":
        with open(filename, 'rb') as f:
            data = tomllib.load(f)
        return cls(species_dict=data['species'], name=data['name'])

    def _build(self) -> dict:
        selected = {}
        for species_id, mol_frac in self.species_dict.items():
            if species_id not in self.all_species:
                raise KeyError(f"Species '{species_id}' not found in species database")
            sp = self.all_species[species_id]
            sp.mol_frac = mol_frac
            selected[species_id] = sp
        return selected
