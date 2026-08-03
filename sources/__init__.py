"""Source registry. Each source exposes a fetch_<source>() -> list[dict]."""

from sources import (
    aicrowd,
    atcoder,
    codechef,
    codeforces,
    devfolio,
    devpost,
    ethglobal,
    hackerearth,
    hackerrank,
    internshala,
    kaggle,
    lablab,
    mlh,
    mygov,
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
    ("codeforces", codeforces.fetch_codeforces),
    ("atcoder", atcoder.fetch_atcoder),
    ("hackerearth", hackerearth.fetch_hackerearth),
    ("ethglobal", ethglobal.fetch_ethglobal),
    ("aicrowd", aicrowd.fetch_aicrowd),
    ("mygov", mygov.fetch_mygov),
]
