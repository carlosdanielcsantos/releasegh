import argparse
import requests
import json
from os import getenv
import re
import subprocess
from rst2ghmd import rst2ghmd

TRASH_FILE = ".releasegh_trash"
WHATSNEW_FILE = 'doc/whats_new.rst'

class Version:
    def __init__(self, version_string):
        self.major, self.minor, self.patch = \
            (int(x) for x in version_string.strip('v').split('.'))

    def bump(self, bump_type):
        new = getattr(self, bump_type) + 1
        setattr(self, bump_type, new)

    def __str__(self):
        return 'v{}.{}.{}'.format(self.major, self.minor, self.patch)


def compose_url(sufix, token):
    return 'https://api.github.com' + sufix + '?access_token=' + token


def git_owner_and_repo():
    r = subprocess.run(["git", "remote", "get-url", "origin"],
                       universal_newlines=True,
                       stdout=subprocess.PIPE)

    match = re.search("git@github.com:(.*)\/(.*).git", r.stdout.strip())
    return match.groups()


def git_branch():
    r = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"],
                       universal_newlines=True,
                       stdout=subprocess.PIPE)

    return r.stdout.strip()


def update_whatsnew(version):
    r = subprocess.run(["sed 's/x\.x\.x/{0}.{1}.{2}/;"
                        "s/x_x_x/{0}_{1}_{2}/' {3} > {4}".
                       format(version.major,
                              version.minor,
                              version.patch,
                              WHATSNEW_FILE,
                              TRASH_FILE)],
                       shell=True,
                       universal_newlines=True,
                       stdout=subprocess.PIPE)


def releasegh(increment, dry_run=True):
    token = getenv("GH_TOKEN")
    owner, repo = git_owner_and_repo()

    get_latest_release = f'/repos/{owner}/{repo}/releases/latest'
    create_release = f'/repos/{owner}/{repo}/releases'

    r = requests.get(compose_url(get_latest_release, token))
    if r.ok:
        repoItem = json.loads(r.text or r.content)
    else:
        raise requests.HTTPError("Error requesting latest release: " +
                                 str(r.status_code))

    branch = git_branch()
    print("Branch =", branch)

    prev_version = Version(repoItem["tag_name"])
    version = Version(repoItem["tag_name"])
    version.bump(increment)
    print("Bump {} ---> {}".format(prev_version, version))

    update_whatsnew(version)

    diff = subprocess.run("diff {} {}".format(WHATSNEW_FILE, TRASH_FILE),
                          shell=True,
                          universal_newlines=True,
                          stdout=subprocess.PIPE)

    print("\n\nWhatsnew diff =")
    print(diff.stdout.strip())
    description = ''.join(rst2ghmd(TRASH_FILE,
                          n_releases=1,
                          min_header_level=0,
                          exclude_min_header=True))
    print("\n\nDescription =")
    print(description)

    payload = {
      "tag_name": str(version),
      "target_commitish": branch,
      "name": str(version),
      "body": description,
      "draft": False,
      "prerelease": False
    }

    if dry_run:
        print("\nTHIS WAS A DRY RUN! "
              "To make an actual release use the --yes flag.")
    else:
        r = requests.post(compose_url(create_release, token), json=payload)
        if r.ok:
            repoItem = json.loads(r.text or r.content)
        else:
            raise requests.HTTPError("Error creating new release: " +
                                     str(r.status_code))


def cli():
    parser = argparse.\
        ArgumentParser(description='make a release to Github',
                       formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('increment', help='Type of increment.',
                        type=str, choices=['major', 'minor', 'patch'])
    parser.add_argument('--yes', help='have to pass this in order to really '
                                      'release to Github, otherwise, '
                                      'only dry runs',
                        action='store_true')

    args = parser.parse_args()

    dry_run = not args.yes

    releasegh(args.increment, dry_run=dry_run)


if __name__ == "__main__":
    cli()
