# Copyright (C) 2015-2022: The University of Edinburgh
#                 Authors: Craig Warren, Antonis Giannopoulos, and John Hartley
#
# This file is part of gprMax.
#
# gprMax is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gprMax is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gprMax.  If not, see <http://www.gnu.org/licenses/>.

from importlib import import_module

import gprMax.config as config
import numpy as np


class CFSParameter:
    """Individual CFS parameter (e.g. alpha, kappa, or sigma)."""

    # Allowable scaling profiles and directions
    scalingprofiles = {'constant': 0, 'linear': 1, 'quadratic': 2, 'cubic': 3,
                       'quartic': 4, 'quintic': 5, 'sextic': 6, 'septic': 7, 'octic': 8}
    scalingdirections = ['forward', 'reverse']

    def __init__(self, ID=None, scaling='polynomial', scalingprofile=None,
                 scalingdirection='forward', min=0, max=0):
        """
        Args:
            ID (str): Identifier for CFS parameter, can be: 'alpha', 'kappa' or 'sigma'.
            scaling (str): Type of scaling, can be: 'polynomial'.
            scalingprofile (str): Type of scaling profile from scalingprofiles.
            scalingdirection (str): Direction of scaling profile from scalingdirections.
            min (float): Minimum value for parameter.
            max (float): Maximum value for parameter.
        """

        self.ID = ID
        self.scaling = scaling
        self.scalingprofile = scalingprofile
        self.scalingdirection = scalingdirection
        self.min = min
        self.max = max


class CFS:
    """CFS term for PML."""

    def __init__(self):
        """
        Args:
            alpha (CFSParameter): alpha parameter for CFS.
            kappa (CFSParameter): kappa parameter for CFS.
            sigma (CFSParameter): sigma parameter for CFS.
        """

        self.alpha = CFSParameter(ID='alpha', scalingprofile='constant')
        self.kappa = CFSParameter(ID='kappa', scalingprofile='constant', min=1, max=1)
        self.sigma = CFSParameter(ID='sigma', scalingprofile='quartic', min=0, max=None)

    def calculate_sigmamax(self, d, er, mr, G):
        """Calculates an optimum value for sigma max based on underlying
            material properties.

        Args:
            d (float): dx, dy, or dz in direction of PML.
            er (float): Average permittivity of underlying material.
            mr (float): Average permeability of underlying material.
            G (class): Grid class instance - holds essential parameters
                        describing the model.
        """

        # Calculation of the maximum value of sigma from http://dx.doi.org/10.1109/8.546249
        m = CFSParameter.scalingprofiles[self.sigma.scalingprofile]
        self.sigma.max = (0.8 * (m + 1)) / (config.sim_config.em_consts['z0'] * d * np.sqrt(er * mr))

    def scaling_polynomial(self, order, Evalues, Hvalues):
        """Applies the polynomial to be used for the scaling profile for
            electric and magnetic PML updates.

        Args:
            order (int): Order of polynomial for scaling profile.
            Evalues (float): numpy array holding scaling profile values for
                                electric PML update.
            Hvalues (float): numpy array holding scaling profile values for
                                magnetic PML update.

        Returns:
            Evalues (float): numpy array holding scaling profile values for
                                electric PML update.
            Hvalues (float): numpy array holding scaling profile values for
                                magnetic PML update.
        """

        tmp = (np.linspace(0, (len(Evalues) - 1) + 0.5, num=2 * len(Evalues))
               / (len(Evalues) - 1)) ** order
        Evalues = tmp[0:-1:2]
        Hvalues = tmp[1::2]

        return Evalues, Hvalues

    def calculate_values(self, thickness, parameter):
        """Calculates values for electric and magnetic PML updates based on
            profile type and minimum and maximum values.

        Args:
            thickness (int): Thickness of PML in cells.
            parameter (CFSParameter): Instance of CFSParameter

        Returns:
            Evalues (float): numpy array holding profile value for electric
                                PML update.
            Hvalues (float): numpy array holding profile value for magnetic
                                PML update.
        """

        # Extra cell of thickness added to allow correct scaling of electric and magnetic values
        Evalues = np.zeros(thickness + 1, dtype=config.sim_config.dtypes['float_or_double'])
        Hvalues = np.zeros(thickness + 1, dtype=config.sim_config.dtypes['float_or_double'])

        if parameter.scalingprofile == 'constant':
            Evalues += parameter.max
            Hvalues += parameter.max

        elif parameter.scaling == 'polynomial':
            Evalues, Hvalues = self.scaling_polynomial(
                CFSParameter.scalingprofiles[parameter.scalingprofile],
                Evalues, Hvalues)
            if parameter.ID == 'alpha':
                Evalues = Evalues * (self.alpha.max - self.alpha.min) + self.alpha.min
                Hvalues = Hvalues * (self.alpha.max - self.alpha.min) + self.alpha.min
            elif parameter.ID == 'kappa':
                Evalues = Evalues * (self.kappa.max - self.kappa.min) + self.kappa.min
                Hvalues = Hvalues * (self.kappa.max - self.kappa.min) + self.kappa.min
            elif parameter.ID == 'sigma':
                Evalues = Evalues * (self.sigma.max - self.sigma.min) + self.sigma.min
                Hvalues = Hvalues * (self.sigma.max - self.sigma.min) + self.sigma.min

        if parameter.scalingdirection == 'reverse':
            Evalues = Evalues[::-1]
            Hvalues = Hvalues[::-1]
            # Magnetic values must be shifted one element to the left after reversal
            Hvalues = np.roll(Hvalues, -1)

        # Extra cell of thickness not required and therefore removed after scaling
        Evalues = Evalues[:-1]
        Hvalues = Hvalues[:-1]

        return Evalues, Hvalues


class PML:
    """Perfectly Matched Layer (PML) Absorbing Boundary Conditions (ABC)"""

    # Available PML formulations:
    # Higher Order RIPML (HORIPML) see: https://doi.org/10.1109/TAP.2011.2180344
    # Multipole RIPML (MRIPML) see: https://doi.org/10.1109/TAP.2018.2823864
    formulations = ['HORIPML', 'MRIPML']

    # PML slabs IDs at boundaries of domain.
    boundaryIDs = ['x0', 'y0', 'z0', 'xmax', 'ymax', 'zmax']

    # Indicates direction of increasing absorption
    # xminus, yminus, zminus - absorption increases in negative direction of x-axis, y-axis, or z-axis
    # xplus, yplus, zplus - absorption increases in positive direction of x-axis, y-axis, or z-axis
    directions = ['xminus', 'yminus', 'zminus', 'xplus', 'yplus', 'zplus']

    def __init__(self, G, ID=None, direction=None, xs=0, xf=0, ys=0, yf=0, zs=0, zf=0):
        """
        Args:
            G (FDTDGrid): Holds essential parameters describing the model.
            ID (str): Identifier for PML slab.
            direction (str): Direction of increasing absorption.
            xs, xf, ys, yf, zs, zf (float): Extent of the PML slab.
        """

        self.G = G
        self.ID = ID
        self.direction = direction
        self.xs = xs
        self.xf = xf
        self.ys = ys
        self.yf = yf
        self.zs = zs
        self.zf = zf
        self.nx = xf - xs
        self.ny = yf - ys
        self.nz = zf - zs

        # Spatial discretisation and thickness
        if self.direction[0] == 'x':
            self.d = self.G.dx
            self.thickness = self.nx
        elif self.direction[0] == 'y':
            self.d = self.G.dy
            self.thickness = self.ny
        elif self.direction[0] == 'z':
            self.d = self.G.dz
            self.thickness = self.nz

        self.CFS = self.G.cfs

        self.initialise_field_arrays()

    def initialise_field_arrays(self):
        """Initialise arrays to store fields in PML."""

        if self.direction[0] == 'x':
            self.EPhi1 = np.zeros((len(self.CFS), self.nx + 1, self.ny, self.nz + 1),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.EPhi2 = np.zeros((len(self.CFS), self.nx + 1, self.ny + 1, self.nz),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.HPhi1 = np.zeros((len(self.CFS), self.nx, self.ny + 1, self.nz),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.HPhi2 = np.zeros((len(self.CFS), self.nx, self.ny, self.nz + 1),
                                  dtype=config.sim_config.dtypes['float_or_double'])
        elif self.direction[0] == 'y':
            self.EPhi1 = np.zeros((len(self.CFS), self.nx, self.ny + 1, self.nz + 1),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.EPhi2 = np.zeros((len(self.CFS), self.nx + 1, self.ny + 1, self.nz),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.HPhi1 = np.zeros((len(self.CFS), self.nx + 1, self.ny, self.nz),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.HPhi2 = np.zeros((len(self.CFS), self.nx, self.ny, self.nz + 1),
                                  dtype=config.sim_config.dtypes['float_or_double'])
        elif self.direction[0] == 'z':
            self.EPhi1 = np.zeros((len(self.CFS), self.nx, self.ny + 1, self.nz + 1),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.EPhi2 = np.zeros((len(self.CFS), self.nx + 1, self.ny, self.nz + 1),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.HPhi1 = np.zeros((len(self.CFS), self.nx + 1, self.ny, self.nz),
                                  dtype=config.sim_config.dtypes['float_or_double'])
            self.HPhi2 = np.zeros((len(self.CFS), self.nx, self.ny + 1, self.nz),
                                  dtype=config.sim_config.dtypes['float_or_double'])

    def calculate_update_coeffs(self, er, mr):
        """Calculates electric and magnetic update coefficients for the PML.

        Args:
            er (float): Average permittivity of underlying material
            mr (float): Average permeability of underlying material
        """

        self.ERA = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.ERB = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.ERE = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.ERF = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.HRA = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.HRB = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.HRE = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])
        self.HRF = np.zeros((len(self.CFS), self.thickness),
                            dtype=config.sim_config.dtypes['float_or_double'])

        for x, cfs in enumerate(self.CFS):
            if not cfs.sigma.max:
                cfs.calculate_sigmamax(self.d, er, mr, self.G)
            Ealpha, Halpha = cfs.calculate_values(self.thickness, cfs.alpha)
            Ekappa, Hkappa = cfs.calculate_values(self.thickness, cfs.kappa)
            Esigma, Hsigma = cfs.calculate_values(self.thickness, cfs.sigma)

            # Define different parameters depending on PML formulation
            if self.G.pmlformulation == 'HORIPML':
                # HORIPML electric update coefficients
                tmp = (2 * config.sim_config.em_consts['e0'] * Ekappa) + self.G.dt * (Ealpha * Ekappa + Esigma)
                self.ERA[x, :] = (2 * config.sim_config.em_consts['e0'] + self.G.dt * Ealpha) / tmp
                self.ERB[x, :] = (2 * config.sim_config.em_consts['e0'] * Ekappa) / tmp
                self.ERE[x, :] = ((2 * config.sim_config.em_consts['e0'] * Ekappa) - self.G.dt
                                  * (Ealpha * Ekappa + Esigma)) / tmp
                self.ERF[x, :] = (2 * Esigma * self.G.dt) / (Ekappa * tmp)

                # HORIPML magnetic update coefficients
                tmp = (2 * config.sim_config.em_consts['e0'] * Hkappa) + self.G.dt * (Halpha * Hkappa + Hsigma)
                self.HRA[x, :] = (2 * config.sim_config.em_consts['e0'] + self.G.dt * Halpha) / tmp
                self.HRB[x, :] = (2 * config.sim_config.em_consts['e0'] * Hkappa) / tmp
                self.HRE[x, :] = ((2 * config.sim_config.em_consts['e0'] * Hkappa) - self.G.dt
                                  * (Halpha * Hkappa + Hsigma)) / tmp
                self.HRF[x, :] = (2 * Hsigma * self.G.dt) / (Hkappa * tmp)

            elif self.G.pmlformulation == 'MRIPML':
                # MRIPML electric update coefficients
                tmp = 2 * config.sim_config.em_consts['e0'] + self.G.dt * Ealpha
                self.ERA[x, :] = Ekappa + (self.G.dt * Esigma) / tmp
                self.ERB[x, :] = (2 * config.sim_config.em_consts['e0']) / tmp
                self.ERE[x, :] = ((2 * config.sim_config.em_consts['e0']) - self.G.dt * Ealpha) / tmp
                self.ERF[x, :] = (2 * Esigma * self.G.dt) / tmp

                # MRIPML magnetic update coefficients
                tmp = 2 * config.sim_config.em_consts['e0'] + self.G.dt * Halpha
                self.HRA[x, :] = Hkappa + (self.G.dt * Hsigma) / tmp
                self.HRB[x, :] = (2 * config.sim_config.em_consts['e0']) / tmp
                self.HRE[x, :] = ((2 * config.sim_config.sim_config.em_consts['e0']) - self.G.dt * Halpha) / tmp
                self.HRF[x, :] = (2 * Hsigma * self.G.dt) / tmp

    def update_electric(self):
        """This functions updates electric field components with the PML correction."""

        pmlmodule = 'gprMax.cython.pml_updates_electric_' + self.G.pmlformulation
        func = getattr(import_module(pmlmodule), 'order' + str(len(self.CFS)) + '_' + self.direction)
        func(self.xs, self.xf, self.ys, self.yf, self.zs, self.zf,
             config.get_model_config().ompthreads, self.G.updatecoeffsE, self.G.ID,
             self.G.Ex, self.G.Ey, self.G.Ez, self.G.Hx, self.G.Hy, self.G.Hz,
             self.EPhi1, self.EPhi2, self.ERA, self.ERB, self.ERE, self.ERF, self.d)

    def update_magnetic(self):
        """This functions updates magnetic field components with the PML correction."""

        pmlmodule = 'gprMax.cython.pml_updates_magnetic_' + self.G.pmlformulation
        func = getattr(import_module(pmlmodule), 'order' + str(len(self.CFS)) + '_' + self.direction)
        func(self.xs, self.xf, self.ys, self.yf, self.zs, self.zf,
             config.get_model_config().ompthreads, self.G.updatecoeffsH, self.G.ID,
             self.G.Ex, self.G.Ey, self.G.Ez, self.G.Hx, self.G.Hy, self.G.Hz,
             self.HPhi1, self.HPhi2, self.HRA, self.HRB, self.HRE, self.HRF, self.d)


class CUDAPML(PML):
    """Perfectly Matched Layer (PML) Absorbing Boundary Conditions (ABC) for
        solving on GPU using CUDA.
    """

    def htod_field_arrays(self):
        """Initialise PML field and coefficient arrays on GPU."""

        import pycuda.gpuarray as gpuarray

        self.ERA_gpu = gpuarray.to_gpu(self.ERA)
        self.ERB_gpu = gpuarray.to_gpu(self.ERB)
        self.ERE_gpu = gpuarray.to_gpu(self.ERE)
        self.ERF_gpu = gpuarray.to_gpu(self.ERF)
        self.HRA_gpu = gpuarray.to_gpu(self.HRA)
        self.HRB_gpu = gpuarray.to_gpu(self.HRB)
        self.HRE_gpu = gpuarray.to_gpu(self.HRE)
        self.HRF_gpu = gpuarray.to_gpu(self.HRF)
        self.EPhi1_gpu = gpuarray.to_gpu(self.EPhi1)
        self.EPhi2_gpu = gpuarray.to_gpu(self.EPhi2)
        self.HPhi1_gpu = gpuarray.to_gpu(self.HPhi1)
        self.HPhi2_gpu = gpuarray.to_gpu(self.HPhi2)

    def set_blocks_per_grid(self):
        """Set the blocks per grid size used for updating the PML field arrays
            on a GPU."""
        self.bpg = (int(np.ceil(((self.EPhi1_gpu.shape[1] + 1) *
                   (self.EPhi1_gpu.shape[2] + 1) *
                   (self.EPhi1_gpu.shape[3] + 1)) / self.G.tpb[0])), 1, 1)

    def get_update_funcs(self, kernelselectric, kernelsmagnetic):
        """Get update functions from PML kernels.

        Args:
            kernelselectric: PyCuda SourceModule containing PML kernels for
                                electric updates.
            kernelsmagnetic: PyCuda SourceModule containing PML kernels for
                                magnetic updates.
        """

        self.update_electric_gpu = kernelselectric.get_function('order' + str(len(self.CFS)) + '_' + self.direction)
        self.update_magnetic_gpu = kernelsmagnetic.get_function('order' + str(len(self.CFS)) + '_' + self.direction)

    def update_electric(self):
        """This functions updates electric field components with the PML
            correction on the GPU.
        """
        self.update_electric_gpu(np.int32(self.xs), np.int32(self.xf),
                                 np.int32(self.ys), np.int32(self.yf),
                                 np.int32(self.zs), np.int32(self.zf),
                                 np.int32(self.EPhi1_gpu.shape[1]),
                                 np.int32(self.EPhi1_gpu.shape[2]),
                                 np.int32(self.EPhi1_gpu.shape[3]),
                                 np.int32(self.EPhi2_gpu.shape[1]),
                                 np.int32(self.EPhi2_gpu.shape[2]),
                                 np.int32(self.EPhi2_gpu.shape[3]),
                                 np.int32(self.thickness),
                                 self.G.ID_gpu.gpudata,
                                 self.G.Ex_gpu.gpudata, self.G.Ey_gpu.gpudata, self.G.Ez_gpu.gpudata,
                                 self.G.Hx_gpu.gpudata, self.G.Hy_gpu.gpudata, self.G.Hz_gpu.gpudata,
                                 self.EPhi1_gpu.gpudata, self.EPhi2_gpu.gpudata,
                                 self.ERA_gpu.gpudata, self.ERB_gpu.gpudata,
                                 self.ERE_gpu.gpudata, self.ERF_gpu.gpudata,
                                 config.sim_config.dtypes['float_or_double'](self.d),
                                 block=self.G.tpb, grid=self.bpg)

    def update_magnetic(self):
        """This functions updates magnetic field components with the PML
            correction on the GPU.
        """
        self.update_magnetic_gpu(np.int32(self.xs), np.int32(self.xf),
                                 np.int32(self.ys), np.int32(self.yf),
                                 np.int32(self.zs), np.int32(self.zf),
                                 np.int32(self.HPhi1_gpu.shape[1]),
                                 np.int32(self.HPhi1_gpu.shape[2]),
                                 np.int32(self.HPhi1_gpu.shape[3]),
                                 np.int32(self.HPhi2_gpu.shape[1]),
                                 np.int32(self.HPhi2_gpu.shape[2]),
                                 np.int32(self.HPhi2_gpu.shape[3]),
                                 np.int32(self.thickness),
                                 self.G.ID_gpu.gpudata,
                                 self.G.Ex_gpu.gpudata, self.G.Ey_gpu.gpudata, self.G.Ez_gpu.gpudata,
                                 self.G.Hx_gpu.gpudata, self.G.Hy_gpu.gpudata, self.G.Hz_gpu.gpudata,
                                 self.HPhi1_gpu.gpudata, self.HPhi2_gpu.gpudata,
                                 self.HRA_gpu.gpudata, self.HRB_gpu.gpudata,
                                 self.HRE_gpu.gpudata, self.HRF_gpu.gpudata,
                                 config.sim_config.dtypes['float_or_double'](self.d),
                                 block=self.G.tpb, grid=self.bpg)

def print_pml_info(G):
    """Information about PMLs.

    Args:
        G (FDTDGrid): Parameters describing a grid in a model.
    """
    # No PML
    if all(value == 0 for value in G.pmlthickness.values()):
        return f'\nPML boundaries [{G.name}]: switched off'

    if all(value == G.pmlthickness['x0'] for value in G.pmlthickness.values()):
        pmlinfo = str(G.pmlthickness['x0'])
    else:
        pmlinfo = ''
        for key, value in G.pmlthickness.items():
            pmlinfo += f'{key}: {value}, '
        pmlinfo = pmlinfo[:-2]

    return f'\nPML boundaries [{G.name}]: {{formulation: {G.pmlformulation}, order: {len(G.cfs)}, thickness (cells): {pmlinfo}}}'


def build_pml(G, key, value):
    """This function builds instances of the PML and calculates the initial
        parameters and coefficients including setting profile
        (based on underlying material er and mr from solid array).

    Args:
        G (FDTDGrid): Parameters describing a grid in a model.
        key (str): Identifier of PML slab.
        value (int): Thickness of PML slab in cells.
    """

    pml_type = CUDAPML if config.sim_config.general['cuda'] else PML

    sumer = 0  # Sum of relative permittivities in PML slab
    summr = 0  # Sum of relative permeabilities in PML slab

    if key[0] == 'x':
        if key == 'x0':
            pml = pml_type(G, ID=key, direction='xminus', xf=value, yf=G.ny, zf=G.nz)
        elif key == 'xmax':
            pml = pml_type(G, ID=key, direction='xplus', xs=G.nx - value, xf=G.nx, yf=G.ny, zf=G.nz)
        G.pmls.append(pml)
        for j in range(G.ny):
            for k in range(G.nz):
                numID = G.solid[pml.xs, j, k]
                material = next(x for x in G.materials if x.numID == numID)
                sumer += material.er
                summr += material.mr
        averageer = sumer / (G.ny * G.nz)
        averagemr = summr / (G.ny * G.nz)

    elif key[0] == 'y':
        if key == 'y0':
            pml = pml_type(G, ID=key, direction='yminus', yf=value, xf=G.nx, zf=G.nz)
        elif key == 'ymax':
            pml = pml_type(G, ID=key, direction='yplus', ys=G.ny - value, xf=G.nx, yf=G.ny, zf=G.nz)
        G.pmls.append(pml)
        for i in range(G.nx):
            for k in range(G.nz):
                numID = G.solid[i, pml.ys, k]
                material = next(x for x in G.materials if x.numID == numID)
                sumer += material.er
                summr += material.mr
        averageer = sumer / (G.nx * G.nz)
        averagemr = summr / (G.nx * G.nz)

    elif key[0] == 'z':
        if key == 'z0':
            pml = pml_type(G, ID=key, direction='zminus', zf=value, xf=G.nx, yf=G.ny)
        elif key == 'zmax':
            pml = pml_type(G, ID=key, direction='zplus', zs=G.nz - value, xf=G.nx, yf=G.ny, zf=G.nz)
        G.pmls.append(pml)
        for i in range(G.nx):
            for j in range(G.ny):
                numID = G.solid[i, j, pml.zs]
                material = next(x for x in G.materials if x.numID == numID)
                sumer += material.er
                summr += material.mr
        averageer = sumer / (G.nx * G.ny)
        averagemr = summr / (G.nx * G.ny)

    pml.calculate_update_coeffs(averageer, averagemr)
