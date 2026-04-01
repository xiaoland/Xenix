# 30 Unit TDD

This layer is for hard local units where code and tests alone are not enough to preserve design intent.

Add a unit TDD only when:

- the unit has high local complexity
- repeated regressions suggest hidden invariants
- the behavior is expensive to rediscover from code history

Do not create unit TDDs for simple or stable modules.
