import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# How skill installers find the support files a SKILL.md uses: a path under one of these folders,
# after "](", a backtick, a quote or whitespace. Hermes Agent rejects the whole install when such a
# path is a folder or a symlink rather than a file.
LOCAL_REF = re.compile(
    r"(?:\]\(|`|(?:^|[\s\"']))((?:references|templates|scripts|assets|examples)/[^\s)`\"'<>]+)", re.MULTILINE)


def skill_md():
    with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as f:
        return f.read()


def test_every_referenced_path_is_a_file():
    refs = {m.rstrip("/.,;:") for m in LOCAL_REF.findall(skill_md())}
    assert refs, "SKILL.md should link the files it uses"
    for ref in sorted(refs):
        path = os.path.join(ROOT, ref)
        assert os.path.isfile(path) and not os.path.islink(path), ref


def test_name_matches_the_folder_and_version_matches_the_cli():
    front = skill_md().split("---")[1]
    name = re.search(r"^name:\s*(\S+)", front, re.M).group(1)
    version = re.search(r"^version:\s*(\S+)", front, re.M).group(1)
    assert name == "telegram-widget-skill"  # the repository, install folder and ClawHub slug
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from tgwidget import __version__
    assert version == __version__
