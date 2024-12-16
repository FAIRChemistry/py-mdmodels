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

- primitive_types
  - Type: string, integer, float, boolean
- complex_types
  - Type: FirstType, SecondType
- array_primitive_types
  - Type: string, integer, float, boolean
  - Multiple: true
- array_complex_types
  - Type: FirstType, SecondType
  - Multiple: true

### FirstType

- value
  - Type: string

### SecondType

- value
  - Type: integer
