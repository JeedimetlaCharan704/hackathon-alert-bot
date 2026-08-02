"""Source registry. Each source exposes a fetch_<source>() -> list[dict]."""

from sources import (
    codechef,
    devfolio,
    devpost,
    hackerrank,
    internshala,
    kaggle,
    lablab,
    mlh,
    reskilll,
    unstop,
)

ALL_SOURCES = [
    ("devfolio", devfolio.fetch_devfolio),
    ("unstop", unstop.fetch_unstop),
    ("reskilll", reskilll.fetch_reskilll),
    ("internshala", internshala.fetch_internshala),
    ("devpost", devpost.fetch_devpost),
    ("lablab", lablab.fetch_lablab),
    ("mlh", mlh.fetch_mlh),
    ("codechef", codechef.fetch_codechef),
    ("hackerrank", hackerrank.fetch_hackerrank),
    ("kaggle", kaggle.fetch_kaggle),
]
