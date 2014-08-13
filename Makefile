all: clean build

build:
	cd src ; \
	zip ../Gmail-for-Alfred.alfredworkflow . -r --exclude=*.DS_Store* --exclude=*.pyc*

clean:
	rm -f *.alfredworkflow