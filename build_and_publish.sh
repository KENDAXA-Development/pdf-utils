#!/bin/bash
set -e
## This script is meant to be used by the CI tool to test, build and publish this python package.
## For usage information run the script with --help
##

# Path to publish the generated python package.
PYPI_REPOSITORY="https://nexus.kendaxa.net/repository/pypi-kx/"
#
## print usage
#function display_usage() {
#    echo "Usage: $0 [options] [--pypi-username <pypi-username> --pypi-password <pypi-password>]"
#    echo -e "\t--skip-test\tDo not run tests."
#    echo -e "\t--pypi-username username for the pypi repository ${PYPI_REPOSITORY}."
#    echo -e "\t--pypi-password password for the pypi repository ${PYPI_REPOSITORY}."
#}
#
## parse parameters
#while test $# -gt 0; do
#    case "$1" in
#        --help|-h)
#            display_usage
#            exit 0
#            ;;
#        --skip-test)
#            skip_test=true
#            shift 1
#            ;;
#        --pypi-username)
#            pypi_username=$2
#            shift 2
#            ;;
#        --pypi-password)
#            pypi_password=$2
#            shift 2
#            ;;
#        *)
#            echo "ERROR Unrecognized option '${1}.'"
#            display_usage
#            exit 1
#            ;;
#        esac
#done
#
#if ! test -v skip_test; then
#    echo "Running tests..."
#    #tox
#fi

#if test -n "${pypi_username}" -a -n "${pypi_password}"; then
    echo "Publishing package..."
    python setup.py sdist
    twine upload --verbose dist/* -u "${pypi_username}" -p "${pypi_password}" --repository-url ${PYPI_REPOSITORY}
#fi

exit 0

