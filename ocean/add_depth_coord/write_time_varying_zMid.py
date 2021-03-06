#!/usr/bin/env python

"""
Write a 3D coordinate "zMid" (optionally with a prefix such as
"timeMonthly_avg_") to an MPAS-Ocean output file.  zMid defines the
positive-up vertical location of each cell center.
"""
# Authors
# -------
# Xylar Asay-Davis

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import xarray
import numpy
import netCDF4
import argparse
import sys
from datetime import datetime


def write_netcdf(ds, fileName):
    '''
    Write an xarray data set to a NetCDF file making use of the _FillValue
    attributes of each variable.  This function should be used for data sets
    opened with mask_and_scale=False.

    Parameters
    ----------
    ds : xarray.Dataset object
        The xarray data set to be written to a file

    fileName : str
        The fileName to write the data set to
    '''
    # Authors
    # -------
    # Xylar Asay-Davis

    encodingDict = {}
    variableNames = list(ds.data_vars.keys()) + list(ds.coords.keys())
    for variableName in variableNames:
        if '_FillValue' in ds[variableName].attrs:
            encodingDict[variableName] = \
                {'_FillValue': ds[variableName].attrs['_FillValue']}
            del ds[variableName].attrs['_FillValue']
        else:
            encodingDict[variableName] = {'_FillValue': None}

    ds.to_netcdf(fileName, encoding=encodingDict)


def compute_zmid(bottomDepth, maxLevelCell, layerThickness):
    """
    Computes zMid given data arrays for bottomDepth, maxLevelCell and
    layerThickness

    Parameters
    ----------
    bottomDepth : ``xarray.DataArray``
        the depth of the ocean bottom (positive)

    maxLevelCell : ``xarray.DataArray``
        the 1-based vertical index of the bottom of the ocean

    layerThickness : ``xarray.DataArray``
        the thickness of MPAS-Ocean layers (possibly as a function of time)

    Returns
    -------
    zMid : ``xarray.DataArray``
        the vertical coordinate defining the middle of each layer, masked below
        the bathymetry
    """
    # Authors
    # -------
    # Xylar Asay-Davis

    nDepth = layerThickness.sizes['depth']

    vertIndex = \
        xarray.DataArray.from_dict({'dims': ('depth',),
                                    'data': numpy.arange(nDepth)})

    layerThickness = layerThickness.where(vertIndex < maxLevelCell)

    thicknessSum = layerThickness.sum(dim='depth')
    thicknessCumSum = layerThickness.cumsum(dim='depth')
    zSurface = -bottomDepth+thicknessSum

    zLayerBot = zSurface - thicknessCumSum

    zMid = zLayerBot + 0.5*layerThickness

    zMid = zMid.where(vertIndex < maxLevelCell)
    zMid = zMid.transpose('Time', 'nCells', 'depth')

    return zMid


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-c", "--coordFileName", dest="coordFileName",
                        type=str, required=False,
                        help="A MPAS-Ocean file with bottomDepth and "
                             "maxLevelCell")
    parser.add_argument("-i", "--inFileName", dest="inFileName", type=str,
                        required=True,
                        help="An input MPAS-Ocean file with some form of"
                             "layerThickness, and also bottomDepth and"
                             "maxLevelCell if no coordinate file is provided.")
    parser.add_argument("-o", "--outFileName", dest="outFileName", type=str,
                        required=True,
                        help="An output MPAS-Ocean file with zMid for each"
                             "time in the input file")
    parser.add_argument("-p", "--prefix", dest="prefix", type=str,
                        required=False, default="",
                        help="A prefix on layerThickness (in) and zMid (out),"
                             "such as 'timeMonthly_avg_'")
    args = parser.parse_args()

    if args.coordFileName:
        coordFileName = args.coordFileName
    else:
        coordFileName = args.inputFileName

    dsCoord = xarray.open_dataset(coordFileName)
    dsCoord = dsCoord.rename({'nVertLevels': 'depth'})

    dsIn = xarray.open_dataset(args.inFileName)
    dsIn = dsIn.rename({'nVertLevels': 'depth'})
    inVarName = '{}layerThickness'.format(args.prefix)
    outVarName = '{}zMid'.format(args.prefix)
    layerThickness = dsIn[inVarName]

    zMid = compute_zmid(dsCoord.bottomDepth, dsCoord.maxLevelCell,
                        layerThickness)

    dsOut = xarray.Dataset()
    dsOut[outVarName] = zMid
    fillValue = netCDF4.default_fillvals['f8']
    dsOut[outVarName] = dsOut[outVarName].where(dsOut[outVarName].notnull(),
                                                other=fillValue)
    dsOut[outVarName].attrs['units'] = 'meters'
    dsOut[outVarName].attrs['positive'] = 'up'
    dsOut[outVarName].attrs['_FillValue'] = fillValue

    time = datetime.now().strftime('%c')

    history = '{}: {}'.format(time, ' '.join(sys.argv))
    dsOut.attrs['history'] = history

    write_netcdf(dsOut, args.outFileName)


if __name__ == '__main__':
    main()
