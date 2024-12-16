### Test

- name
  - Type: string
  - PK: true
- float_field
  - Type: float
- string_field
  - Type: string
- boolean_field
  - Type: boolean
- skipped_multiple_field
  - Type: string[]
- single_complex_field
  - Type: Nested
- nested_array_field
  - Type: Nested[]
- some_other_field
  - Type: SomeOther

### Nested

- value
  - Type: string
- other_ref
  - Type: string
  - References: Test.some_other_field.name

### SomeOther

- name
  - Type: string
  - PK: true
