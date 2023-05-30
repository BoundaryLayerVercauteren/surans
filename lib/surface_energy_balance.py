# standard imports
import matplotlib.pyplot as plt
from tqdm import tqdm
from fenics import *
import numpy as np
import h5py

# project related imports
from lib import fenics_utility_functions as fut 
from lib import write_out_functions as wo
from lib import utility_functions as ut


def RHS_surf_balance_euler(x0, fparams, params, Ts, ks, u_now, v_now, Kh_now):
    
    # unroll params
    C_g  = params.C_g
    sig  = params.sig
    k_m  = params.k_m
    dt   = params.dt
    th_m = params.theta_m
    
    # Turb heat flux at the ground
    H0 = get_heat_flux_at_ground(fparams, params, Ts, u_now, v_now, Kh_now)
    
    #  Temperature at the boundary layer top
    # T_a = get_temp_at_BL_top(ks, Ts)     

    # Calculate long-wave incoming radiation
    # I = I_lw_radiation(T_a, params)
        
    return x0 + (1.0/C_g*(params.R_n - H0)  - k_m * (x0 - th_m)) * dt
    

def get_heat_flux_at_ground(fparams, params, Ts, u_now, v_now, Kh_now):
    
    # unroll params
    rho   = params.rho
    C_p   = params.C_p
    kappa = params.kappa
    z0    = params.z0
    z0h   = params.z0h
    
    # calc some varibles for the surface balance equation
    u_star, theta_star, Pr_turb = calc_ground_varibles(fparams, params, Ts, u_now, v_now, Kh_now)
        
    return -rho * C_p * theta_star * u_star * Pr_turb / kappa * np.log(z0/z0h)

def get_temp_at_BL_top(ks, Ts):
    
    ks_array = ks.vector().get_local()
    m_w1     = np.max(ks_array)
    lim_m_w1 = 0.05 * m_w1                          # 5 % of the maximum tke
    ind_h    = ut.find_nearest(ks_array, lim_m_w1)        
        
    return Ts.vector().get_local()[ind_h]


def calc_ground_varibles(fparams, params, Ts, u_now, v_now, Kh_now):
    
    u  = u_now[1]
    v  = v_now[1]
    Kh = Kh_now[1]
    
    # the value of these variable is at the ground level (z = 0)
    u_star     = u_star_at_the_ground(fparams.z, u, v, params)
    theta_star = theta_star_at_the_ground(project(Ts.dx(0), fparams.Q), Kh, u_star)
    Pr_turb    = Pr_turb_at_the_ground(fparams, params)
        
    return u_star, theta_star, Pr_turb


def update_tke_at_the_surface(fparams, params, u_now, v_now):

    u = u_now[1]
    v = v_now[1]
    
    fparams.k_D_low.value = np.max([k_at_the_ground(params, fparams.z, u, v), params.min_tke])
    

def u_star_at_the_ground(z, u_z1, v_z1, params):
    V_z1  = np.sqrt( u_z1**2 + v_z1**2 ) 
    return params.kappa / np.log(z[1][0]/z[0][0]) * V_z1


def theta_star_at_the_ground(grad_T, K_h, u_star):
    # cast the gradient to numpy 
    get_grad_T =  np.flipud( grad_T.vector().get_local() )
    
    # get the flux for the full domain
    temp_turm_flux = K_h * get_grad_T
    
    # use flux at z1 (the lowest is "z0") to calc theta_star
    # the input "u_star" is the estimate from z1 height value
    theta_star = temp_turm_flux[1] / u_star
    
    return theta_star


def Pr_turb_at_the_ground(fparams, params):
    # input is a fenics variable
    full_Pr = project( fut.f_m(fparams, params) / fut.f_h(fparams, params), fparams.Q)
    
    # cast to numpy array
    get_full_Pr =  np.flipud( full_Pr.vector().get_local() )
    return get_full_Pr[0]


def k_at_the_ground(params, z, u_z1, v_z1, _f_m=0.087):
    return u_star_at_the_ground(z, u_z1, v_z1, params)**2/np.sqrt(_f_m)


def I_lw_radiation(T_a, params):
    Qc  = params.Qc  # the cloud fraction
    Qa  = params.Qa  # specific humidity [g kg^-1]
    sig = params.sig # non-dimensional Stefan-Boltzmann constant

    # Calculate long-wave incoming radiation from the top of the ABL (according to Maroneze 2019)
    return sig*(Qc + 0.67*(1-Qc)*(1670*Qa)**0.08)*T_a**4