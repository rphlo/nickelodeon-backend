#! /usr/bin/env bash
coverage run --source=nickelodeon manage.py test
coverage report
