.PHONY: build clean

build:
	uv sync

clean:
	rm -rf .venv
