"""Allow explicit startup with ``python -m portable_agent``."""

from .cli import main


raise SystemExit(main())
