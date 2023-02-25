import nox
from nox.sessions import Session


nox.options.sessions = "black", "flake8", "mypy", "unittests"


@nox.session(python=False)
def unittests(session: Session) -> None:
    session.run("pip", "install", "-r", "requirements.txt")
    session.run(
        "python", "-m", "unittest", "discover", "-s", "tests", "-t", "."
    )


@nox.session(python=False)
def black(session: Session) -> None:
    session.run("black", "src/pyiak_instr", "--line-length=78")


@nox.session(python=False)
def flake8(session: Session) -> None:
    session.run("flake8", "src/pyiak_instr", "--extend-ignore", "E203")


@nox.session(python=False)
def mypy(session: Session):
    session.run(
        "mypy",
        "src/pyiak_instr",
        "--config-file=mypy.ini",
    )
