#!/usr/bin/env bash
pipenv run pyinstaller -F --hidden-import '_sysconfigdata_m' ../AssetLabelGenerator/mkassetlabel.py