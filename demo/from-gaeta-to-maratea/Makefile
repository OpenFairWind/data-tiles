PYTHON ?= python3
CONFIG := config.json
WORK := work

.PHONY: all acquire build verify clean
all: acquire build verify

acquire:
	$(PYTHON) -m datatiles.demo acquire --config $(CONFIG) --work $(WORK)

build:
	$(PYTHON) -m datatiles.demo build --config $(CONFIG) --work $(WORK)

verify:
	$(PYTHON) -m datatiles.demo verify --config $(CONFIG) --work $(WORK)

clean:
	$(PYTHON) -m datatiles.demo clean --config $(CONFIG) --work $(WORK)
