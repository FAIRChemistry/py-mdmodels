# SQL Basic Example

This example demonstrates how to use the mdmodels library to create tables in a SQL database and insert data into them. We are using the following data model:

```mermaid
classDiagram
    class ChemicalProject {
        string title
        Molecule[] molecules
        Reaction[] reactions
        Experiment[] experiments
    }

    class Author {
        string orcid
        string name
    }

    class Molecule {
        string id
        string name
        string formula
    }

    class Experiment {
        string id
        Concentration[] initial_concentrations
    }

    class Concentration {
        string molecule_id
        number value
        string unit
    }

    class Reaction {
        string id
        string name
        Element[] educts
        Element[] products
    }

    class Element {
        string molecule_id
        number stoichiometry
    }

    class KineticModel {
        string molecule_id
        string equation
    }

    ChemicalProject --> Molecule
    ChemicalProject --> Reaction
    ChemicalProject --> Experiment
    ChemicalProject --> Author
    Experiment --> Concentration
    Concentration <-- Molecule
    Reaction --> Element
    Element <-- Molecule
    Molecule --> KineticModel
    ChemicalProject <-- KineticModel
```

---

### ChemicalProject

This object represents a chemical project and serves as the top-level container for managing various aspects of a research project. It organizes the project's title, associated molecules, reactions, and experiments, providing a structured overview of the entire chemical workflow.

- title
  - Type: string
  - Description: The name/title of the project.
  - PK: true
- authors
  - Type: [Author](#author)[]
  - Description: The authors of the project.
- molecules
  - Type: [Molecule](#molecule)[]
  - Description: The molecules used in the project.
- reactions
  - Type: [Reaction](#reaction)[]
  - Description: The reactions in the project.
- experiments
  - Type: [Experiment](#experiment)[]
  - Description: The experiments in the project.
- kinetic_models
  - Type: [KineticModel](#kineticmodel)[]
  - Description: The kinetic models in the project.

---

### Author

- orcid
  - Type: string
  - Description: The ORCID of the author.
  - PK: true
- name
  - Type: string
  - Description: The name of the author.

---

### Molecule

- id
  - Type: string
  - Description: The identifier of the molecule.
- name
  - Type: string
  - Description: The name of the molecule.
- formula
  - Type: string
  - Description: The formula of the molecule.

---

### Experiment

- id
  - Type: string
  - Description: The identifier of the experiment.
- initial_concentrations
  - Type: [Concentration](#concentration)[]
  - Description: The initial concentrations of the molecules in the experiment.

---

### Concentration

- molecule_id
  - Type: string
  - Description: The identifier of the molecule.
  - References: ChemicalProject.molecules.id
- value
  - Type: number
  - Description: The concentration of the molecule.
- unit
  - Type: string
  - Description: The unit of the concentration.

---

### Reaction

- id
  - Type: string
  - Description: The identifier of the reaction.
- name
  - Type: string
  - Description: The name of the reaction.
- educts
  - Type: [Element](#element)[]
  - Description: The reactants of the reaction.
- products
  - Type: [Element](#element)[]
  - Description: The products of the reaction.

---

### Element

- molecule_id
  - Type: string
  - Description: The identifier of the molecule.
  - References: ChemicalProject.molecules.id
- stoichiometry
  - Type: number
  - Description: The stoichiometry of the reactant.

---

### KineticModel

- molecule_id
  - Type: string
  - Description: The identifier of the molecule.
  - References: ChemicalProject.molecules.id
- equation
  - Type: string
  - Description: The equation of the kinetic model.
