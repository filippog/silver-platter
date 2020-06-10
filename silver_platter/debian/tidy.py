#!/usr/bin/python
# Copyright (C) 2019 Jelmer Vernooij <jelmer@jelmer.uk>
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

from breezy.trace import note

from .changer import (
    run_changer,
    run_mutator,
    DebianChanger,
    ChangerResult,
    setup_multi_parser as setup_changer_parser,
    )

from .lintian import LintianBrushChanger
from .multiarch import MultiArchHintsChanger


BRANCH_NAME = 'tidy'


class TidyChanger(DebianChanger):

    SUBCHANGERS = [
        LintianBrushChanger,
        MultiArchHintsChanger,
        ]

    def __init__(self) -> None:
        self.subchangers = [kls() for kls in self.SUBCHANGERS]

    @classmethod
    def setup_parser(cls, parser):
        pass

    @classmethod
    def from_args(cls, args):
        return cls()

    def suggest_branch_name(self):
        return BRANCH_NAME

    def make_changes(self, local_tree, subpath, update_changelog, committer,
                     base_proposal=None):
        result = {}
        tags = set()
        sufficient_for_proposal = False
        auxiliary_branches = set()
        for subchanger in self.subchangers:
            subresult = (
                subchanger.make_changes(
                    local_tree, subpath, update_changelog, committer))
            result[subchanger] = subresult.mutator
            if subresult.sufficient_for_proposal:
                sufficient_for_proposal = True
            if subresult.tags:
                tags.update(subresult.tags)
            if tags.auxiliary_branches:
                auxiliary_branches.update(subresult.auxiliary_branches)

        commit_items = []
        for subchanger in result:
            if isinstance(subchanger, LintianBrushChanger):
                commit_items.append('fix some lintian tags')
            if isinstance(subchanger, MultiArchHintsChanger):
                commit_items.append('apply multi-arch hints')
        proposed_commit_message = (', '.join(commit_items) + '.').capitalize()

        return ChangerResult(
            mutator=result,
            description='Fix various small issues.',
            tags=tags, auxiliary_branches=auxiliary_branches,
            sufficient_for_proposal=sufficient_for_proposal,
            proposed_commit_message=proposed_commit_message)

    def get_proposal_description(
            self, result, description_format, existing_proposal):
        entries = []
        for subchanger, memo in result.items():
            # TODO(jelmer): Does passing existing proposal in here work?
            entries.append(subchanger.get_proposal_description(
                memo, description_format, existing_proposal))
        return '\n'.join(entries)

    def describe(self, result, publish_result):
        if publish_result.is_new:
            note('Create merge proposal: %s', publish_result.proposal.url)
        elif result:
            note('Updated proposal %s', publish_result.proposal.url)
        else:
            note('No new fixes for proposal %s', publish_result.proposal.url)


def main(args):
    changer = TidyChanger.from_args(args)

    return run_changer(changer, args)


def setup_parser(parser):
    setup_changer_parser(parser)
    TidyChanger.setup_parser(parser)


if __name__ == '__main__':
    import sys
    sys.exit(run_mutator(TidyChanger))
