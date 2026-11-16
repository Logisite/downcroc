---
term: interpreter links
see_also: [venv, managed-install, repair]
---

The small links named `python`, `python3`, and `pythonX.Y` inside the [[venv]] `bin` directory. They point at the Python interpreter that runs downcroc. When a system upgrade removes that interpreter, the links dangle or loop and downcroc will not start. [[repair]] points them at a Python that exists.

More: [repair](../part-ii/26-repair/repair.md)
