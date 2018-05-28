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
    def __init__(self, version_string, names=('major', 'minor', 'patch')):
        self.names = names

        self.__version = [int(x) for x in version_string.strip('v').split('.')]

        if len(self.names) != len(self.__version):
            raise ValueError("names size and version string must match")

    def __getattr__(self, item):
        if item in self.names:
            return self.__version[self.names.index(item)]

    def bump(self, bump_type):
        i = self.names.index(bump_type)
        self.__version[i] += 1
        self.__version[(i + 1):] = [0]*len(self.__version[(i + 1):])

    def __str__(self):
        return ('v' + '.'.join(['{}'] * len(self.__version))
                ).format(*self.__version)


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
    with open(WHATSNEW_FILE, 'r') as fd:
        lines = fd.readlines()

    i_ref = [l.find('x_x_x') > -1 for l in lines].index(True)

    lines[i_ref] = lines[i_ref].replace('x_x_x',
                                        '{0}_{1}_{2}'.format(version.major,
                                                             version.minor,
                                                             version.patch))

    i_title = [l.find('x.x.x') > -1 for l in lines].index(True)

    lines[i_title] = lines[i_title].replace('x.x.x',
                                            '{0}.{1}.{2}'.format(version.major,
                                                                 version.minor,
                                                                 version.patch))

    lines[i_title + 1] = '=' * (len(lines[i_title]) - 1) + '\n'

    with open(TRASH_FILE, 'w') as fd:
        fd.writelines(lines)


def whatsnew_diff():
    r = subprocess.run("diff {} {}".format(WHATSNEW_FILE, TRASH_FILE),
                       shell=True,
                       universal_newlines=True,
                       stdout=subprocess.PIPE)

    return r.stdout.strip()


def get_latest_release_md():
    description = ''.join(rst2ghmd(TRASH_FILE,
                          n_releases=1,
                          min_header_level=0,
                          exclude_min_header=True))

    return description


def push_before_release(version, dry_run):
    commands = [
        "cp {} {}".format(TRASH_FILE, WHATSNEW_FILE),
        "git add {}".format(WHATSNEW_FILE),
        "git commit -m 'Release {}'".format(version),
        "git push"
    ]

    if dry_run:
        print("Would call: ")
        [print(c) for c in commands]

    else:
        [subprocess.run(c, shell=True) for c in commands]


def wipe_trash():
    subprocess.run("rm {}".format(TRASH_FILE), shell=True)


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

    print("\n\nWhatsnew diff =")
    print(whatsnew_diff())

    description = get_latest_release_md()
    print("\n\nDescription =")
    print(description)

    push_before_release(version, dry_run)

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

    wipe_trash()


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
