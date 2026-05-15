.PHONY: build
.PHONY: clean
.PHONY: extraclean

build:
	docker-compose up

clean:
	rm -Rf dist
	docker-compose down

extraclean:	clean
	docker rmi csi_properties:latest

