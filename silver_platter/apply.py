#!/usr/bin/python
# Copyright (C) 2021 Jelmer Vernooij <jelmer@jelmer.uk>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from dataclasses import dataclass, field
import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Optional, Dict, List, Tuple
from breezy.commit import PointlessCommit
from breezy.workspace import reset_tree, check_clean_tree
from breezy.workingtree import WorkingTree


class ScriptMadeNoChanges(Exception):
    "Script made no changes."


class ScriptFailed(Exception):
    """Script failed to run."""


@dataclass
class CommandResult(object):

    description: Optional[str] = None
    value: Optional[int] = None
    context: Dict[str, str] = field(default_factory=dict)
    tags: List[Tuple[str, bytes]] = field(default_factory=list)
    old_revision: Optional[bytes] = None
    new_revision: Optional[bytes] = None

    @classmethod
    def from_json(cls, data):
        if 'tags' in data:
            tags = []
            for name, revid in data['tags']:
                tags.append((name, revid.encode('utf-8')))
        else:
            tags = None
        return cls(
            value=data.get('value', None),
            context=data.get('context', {}),
            description=data.get('description'),
            tags=tags)


def script_runner(
    local_tree: WorkingTree, script: str, commit_pending: Optional[bool] = None,
    resume_metadata=None, subpath: str = ''
) -> CommandResult:
    """Run a script in a tree and commit the result.

    This ignores newly added files.

    Args:
      local_tree: Local tree to run script in
      script: Script to run
      commit_pending: Whether to commit pending changes
        (True, False or None: only commit if there were no commits by the
         script)
    """
    env = dict(os.environ)
    env['SVP_API'] = '1'
    last_revision = local_tree.last_revision()
    orig_tags = local_tree.branch.tags.get_tag_dict()
    with tempfile.TemporaryDirectory() as td:
        env['SVP_RESULT'] = os.path.join(td, 'result.json')
        if resume_metadata:
            env['SVP_RESUME'] = os.path.join(td, 'resume-metadata.json')
            with open(env['SVP_RESUME'], 'w') as f:
                json.dump(f, resume_metadata)
        p = subprocess.Popen(
            script, cwd=local_tree.abspath(subpath), stdout=subprocess.PIPE, shell=True,
            env=env)
        (description_encoded, err) = p.communicate(b"")
        if p.returncode != 0:
            raise ScriptFailed(script, p.returncode)
        try:
            with open(env['SVP_RESULT'], 'r') as f:
                result = CommandResult.from_json(json.load(f))
        except FileNotFoundError:
            result = CommandResult()
    if not result.description:
        result.description = description_encoded.decode()
    new_revision = local_tree.last_revision()
    if result.tags is None:
        result.tags = []
        for name, revid in local_tree.branch.tags.get_tag_dict().items():
            if orig_tags.get(name) != revid:
                result.tags.append((name, revid))
    if last_revision == new_revision and commit_pending is None:
        # Automatically commit pending changes if the script did not
        # touch the branch.
        commit_pending = True
    if commit_pending:
        try:
            new_revision = local_tree.commit(result.description, allow_pointless=False)
        except PointlessCommit:
            pass
    if new_revision == last_revision:
        raise ScriptMadeNoChanges()
    result.old_revision = last_revision
    result.new_revision = local_tree.last_revision()
    return result


def main(argv: List[str]) -> Optional[int]:  # noqa: C901
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", help="Path to script to run.", type=str,
        nargs='?')
    parser.add_argument(
        "--diff", action="store_true", help="Show diff of generated changes."
    )
    parser.add_argument(
        "--commit-pending",
        help="Commit pending changes after script.",
        choices=["yes", "no", "auto"],
        default=None,
        type=str,
    )
    parser.add_argument(
        "--verify-command", type=str, help="Command to run to verify changes."
    )
    parser.add_argument(
        "--recipe", type=str, help="Recipe to use.")
    args = parser.parse_args(argv)

    if args.recipe:
        from .recipe import Recipe
        recipe = Recipe.from_path(args.recipe)
    else:
        recipe = None

    if args.commit_pending:
        commit_pending = {"auto": None, "yes": True, "no": False}[args.commit_pending]
    elif recipe:
        commit_pending = recipe.commit_pending
    else:
        commit_pending = None

    if args.command:
        command = args.command
    elif recipe.command:
        command = recipe.command
    else:
        logging.exception('No command specified.')
        return 1

    local_tree, subpath = WorkingTree.open_containing('.')

    check_clean_tree(local_tree)

    try:
        result = script_runner(
            local_tree, script=command, commit_pending=commit_pending,
            subpath=subpath)

        if result.description:
            logging.info('Succeeded: %s', result.description)

        if args.verify_command:
            try:
                subprocess.check_call(
                    args.verify_command, shell=True, cwd=local_tree.abspath(subpath)
                )
            except subprocess.CalledProcessError:
                logging.exception("Verify command failed.")
                return 1
    except Exception:
        reset_tree(local_tree, subpath)
        raise

    if args.diff:
        from breezy.diff import show_diff_trees
        old_tree = local_tree.revision_tree(result.old_revision)
        new_tree = local_tree.revision_tree(result.new_revision)
        show_diff_trees(
            old_tree,
            new_tree,
            sys.stdout.buffer,
            old_label='old/',
            new_label='new/')
    return 0