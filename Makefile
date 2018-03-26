all: clean build

build:
	cd src ; \
	zip ../Gmail-Client-for-Alfred.alfredworkflow . -r --exclude=*.DS_Store* --exclude=*.pyc*

clean:
	rm -f *.alfredworkflow

update-lib:
	/usr/bin/python -m pip install --target src --upgrade Alfred-Workflow
	rm -rf src/Alfred_Workflow-*.dist-info/
	rm -rf src/Alfred_Workflow-*.egg-info/
