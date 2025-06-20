.PHONY: format
format:
	uv tool run ruff check --fix
	uv tool run isort .