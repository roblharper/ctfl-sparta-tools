from species import Species


def read_species_data(filename="species.list"):
    species_dict = {}

    with open(filename) as f:
        lines = f.readlines()

    start = next(i for i, l in enumerate(lines) if l.strip().startswith("# charge")) + 2

    for line in lines[start:]:
        if not line.strip():
            continue

        data = line.split()
        species_id = data[0]
        values = list(map(float, data[1:]))

        species_dict[species_id] = Species(species_id, *values)

    return species_dict


def read_collision_data(species_dict : dict[str, Species], filename="collision.list"):

    with open(filename) as f:
        lines = f.readlines()

    start = next(i for i, l in enumerate(lines) if l.strip().startswith("# MW B")) + 2

    for line in lines[start:]:
        if not line.strip():
            continue

        data = line.split()
        species_id = data[0]
        values = list(map(float, data[1:]))

        if species_id in species_dict:
            s = species_dict[species_id]
            (
                s.diameter,
                s.omega,
                s.tref,
                s.alpha,
                s.rotc1,
                s.rotc2,
                s.birdc1,
                s.birdc2,
                s.MWA,
                s.MWB,
            ) = values

    return species_dict