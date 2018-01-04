#!/usr/bin/env bash
pipenv run pyinstaller --hidden-import '_sysconfigdata_m' ../AssetLabelGenerator/mkassetlabel.py