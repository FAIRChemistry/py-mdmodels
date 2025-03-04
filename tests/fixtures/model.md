---
id-field: true
repo: "https://www.github.com/my/repo/"
prefix: "tst"
prefixes:
  schema: http://schema.org/
nsmap:
  tst: http://example.com/test/
---

### Test

- **name**
  - Type: Identifier
  - Term: schema:hello
  - Description: The name of the test.
  - XML: @name
- to_reference
  - Type: string[]
- number
  - Type: float
  - Term: schema:one
  - XML: @number
  - Default: 1.0
- single_object
  - Type: Nested
  - Term: schema:something
  - XML: Nested
- nested_array
  - Type: [Nested](#nested)[]
  - Term: schema:something
  - XML: NestedArray
- ontology
  - Type: Ontology

### Nested

- reference
  - Type: string
  - References: Test.to_reference
  - Regex: ^[a-z]+$
- names
  - Type: string[]
  - Term: schema:hello
  - XML: name
- number
  - Type: float
  - Term: schema:one
  - XML: @number
  - Minimum: 0

## Enumerations

### Ontology

Ontology endpoints for different types of sequences.

```
GO = "https://amigo.geneontology.org/amigo/term/"
SIO = "http://semanticscience.org/resource/"
ECO = "https://www.evidenceontology.org/term/"
```
