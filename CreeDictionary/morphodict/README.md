morphodict
==========

The **morpho**logical **dict**ionary application.


Usage
-----

Add it to the `INSTALLED_APPS` in your Django settings:

```python
INSTALLED_APPS = [
    # other apps
    "morphodict.apps.MorphodictConfig",
]
```

Add configs

MORPHODICT_SOURCES

```python

# sources for the dictionary
MORPHODICT_SOURCES = [
    {
        "abbrv": "MD",
        "title": "Maskwacîs Dictionary of Cree Words / Nehiyaw Pîkiskweninisa",
        "editor": "Maskwaschees Cultural College",
        "publisher": "Maskwachees Cultural College",
        "year": 2009,
        "city": "Maskwacîs, Alberta",
    },
    {
        "abbrv": "CW",
        "title": "nêhiyawêwin : itwêwina / Cree : Words",
        "editor": "Arok Wolvengrey",
        "year": 2001,
        "publisher": "Canadian Plains Research Center",
        "city": "Regina, Saskatchewan",
    },
    {
        "abbrv": "AE",
        "title": "Alberta Elders' Cree Dictionary/"
        "alperta ohci kehtehayak nehiyaw otwestamâkewasinahikan",
        "author": "Nancy LeClaire, George Cardinal",
        "editor": "Earle H. Waugh",
        "year": 2002,
        "publisher": "The University of Alberta Press",
        "city": "Edmonton, Alberta",
    },
]
```