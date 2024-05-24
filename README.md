# tacos-cli
**TACOS: Types And Crosswalks Organized for Schema mapping and management**

Work-in-progress CLI tool to interact with FAIRCORE4EOSC [MSCR](https://faircore4eosc.eu/eosc-core-components/metadata-schema-and-crosswalk-registry-mscr) and [DTR](https://faircore4eosc.eu/eosc-core-components/eosc-data-type-registry-dtr) -services.


## Install

```
$ git clone https://github.com/EUDAT-B2SHARE/tacos-cli.git
$ cd tacos-cli
$ pip install -r requirements.txt
```


## Usage 

##### For DTR interaction
`$ python tacos-cli.py dtr [OPTIONS] COMMAND [ARGS]`.

##### Possible DTR commands:
```
$ python tacos-cli.py dtr --help
Usage: tacos-cli.py dtr [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  fetch-json-schema  Fetch a Schema from DTR and output it.
  fetch-schema       Fetch a Schema from DTR in JSON-Schema format and...
  fetch-type         Fetch DTR Type information and output it.
```

##### For MSCR interaction
`$ python tacos-cli.py mscr [OPTIONS] COMMAND [ARGS`.

##### Possible MSCR commands:
```
$ python tacos-cli.py mscr --help
Usage: tacos-cli.py mscr [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  add-types        Add DTR Type information to metadata schema in MSCR.
  register-schema  Register metadata schema into MSCR.
```