## The problem formulation package for universal energy management system
# The modelling language is borrowed from PyPower, which is a Python-version matpower.
# Mat-power is a popular solution package for simulation analysis and study in power system, which is originally for matlab.
# The detail about Pypower is refered to the following link.
# https://pypi.python.org/pypi/PYPOWER
# The modelling in UEMS has been extended according to similar methods.
# When linear models are used, piece-wise linear cost function is used to optimize multiple load curves.

from numpy import array, vstack, zeros
import numpy
from configuration import configuration_eps


# The data structure is imported from numpy.
# The relaxation is to relax the boundary variables
class problem_formulation_set_points_tracing():
    ## Reformulte the information model to system level
    def problem_formulation_local(*args):
        from configuration import configuration_time_line
        from modelling.power_flow.idx_opf_set_points_tracing import PG, QG, RG, PUG, QUG, RUG, PBIC_AC2DC, PBIC_DC2AC, \
            QBIC, PESS_C, \
            PESS_DC, RESS, EESS, PMG, PMG_negative, PMG_positive, PUG_negative, PUG_positive, SOC_negative, \
            SOC_positive, NX
        model = args[0]  # If multiple models are inputed, more local ems models will be formulated
        ## The feasible optimal problem formulation
        lb = zeros(NX)
        ub = zeros(NX)
        ## Update lower boundary
        lb[PG] = model["DG"]["PMIN"]
        lb[QG] = model["DG"]["QMIN"]
        lb[RG] = model["DG"]["PMIN"]

        lb[PUG] = model["UG"]["PMIN"]
        lb[QUG] = model["UG"]["QMIN"]
        lb[RUG] = model["UG"]["PMIN"]

        lb[PBIC_AC2DC] = 0
        lb[PBIC_DC2AC] = 0
        lb[QBIC] = -model["BIC"]["CAP"]

        lb[PESS_C] = 0
        lb[PESS_DC] = 0
        lb[RESS] = 0
        lb[EESS] = model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"]
        # Update the relaxations
        lb[PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line
        lb[PMG_negative] = 0
        lb[PMG_positive] = 0
        lb[PUG_positive] = 0
        lb[PUG_negative] = 0
        lb[SOC_positive] = 0
        lb[SOC_negative] = 0
        ## Update lower boundary
        ub[PG] = model["DG"]["PMAX"]
        ub[QG] = model["DG"]["QMAX"]
        ub[RG] = model["DG"]["PMAX"]

        ub[PUG] = model["UG"]["PMAX"]
        ub[QUG] = model["UG"]["QMAX"]
        ub[RUG] = model["UG"]["PMAX"]

        ub[PBIC_AC2DC] = model["BIC"]["CAP"]
        ub[PBIC_DC2AC] = model["BIC"]["CAP"]
        ub[QBIC] = model["BIC"]["CAP"]

        ub[PESS_C] = model["ESS"]["PMAX_CH"]
        ub[PESS_DC] = model["ESS"]["PMAX_DIS"]
        ub[RESS] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]
        ub[EESS] = model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"]

        ub[PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line

        ub[PMG_positive] = 0  # This boundary information will ne updated to the
        ub[PMG_negative] = 0
        ub[PUG_positive] = model["UG"]["PMAX"]
        ub[PUG_negative] = model["UG"]["PMAX"]
        ub[SOC_positive] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]  # The up relaxation of SOC, this is
        ub[SOC_negative] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]  # The up relaxation of SOC
        ## Constraints set
        # 1) Power balance equation
        Aeq = zeros(NX)
        beq = []
        Aeq[PG] = 1
        Aeq[PUG] = 1
        Aeq[PBIC_AC2DC] = -1
        beq.append(model["Load_ac"]["PD"] + model["Load_uac"]["PD"])
        # 2) DC power balance equation
        Aeq_temp = zeros(NX)
        Aeq_temp[PBIC_AC2DC] = model["BIC"]["EFF_AC2DC"]
        Aeq_temp[PBIC_DC2AC] = -1
        Aeq_temp[PESS_C] = -1
        Aeq_temp[PESS_DC] = 1
        Aeq_temp[PMG] = -1
        Aeq = vstack([Aeq, Aeq_temp])
        beq.append(model["Load_dc"]["PD"] + model["Load_udc"]["PD"] - model["PV"]["PG"] - model["WP"]["PG"])
        ## This erro is caused by the information collection, and the model formulated is list. This is easy for the use
        # 3) Reactive power balance equation
        Aeq_temp = zeros(NX)
        Aeq_temp[QG] = 1
        Aeq_temp[QUG] = 1
        Aeq_temp[QBIC] = 1
        Aeq = vstack([Aeq, Aeq_temp])
        # beq.append(0)
        beq.append(model["Load_ac"]["QD"] + model["Load_uac"]["QD"])
        # 4) Energy storage system
        Aeq_temp = zeros(NX)
        Aeq_temp[EESS] = 1
        Aeq_temp[PESS_C] = -model["ESS"]["EFF_CH"] * configuration_time_line.default_time["Time_step_opf"] / 3600
        Aeq_temp[PESS_DC] = 1 / model["ESS"]["EFF_DIS"] * configuration_time_line.default_time[
            "Time_step_opf"] / 3600
        Aeq = vstack([Aeq, Aeq_temp])
        beq.append(model["ESS"]["SOC"] * model["ESS"]["CAP"])
        # Inequality constraints
        # 1) PG + RG <= PGMAX
        # 2) PG - RG >= PGMIN
        # 3) PUG + RUG <= PUGMAX
        # 4) PUG - RUG >= PUGMIN
        # 5) PESS_DC - PESS_C + RESS <= PESS_DC_MAX
        # 6) PESS_DC - PESS_C - RESS >= -PESS_C_MAX
        # 7) EESS - RESS*delta >= EESSMIN
        # 8) EESS + RESS*delta <= EESSMAX
        # 9) RG + RUG + RESS >= sum(Load)*beta + sum(PV)*beta_pv + sum(WP)*beta_wp
        # 10) PUG-PUG_positive<=PUG_SET_POINT
        # 11) PUG+PUG_negative>=PUG_SET_POINT
        # 12) PMG-PMG_positive<=PMG_SET_POINT
        # 13) PMG+PMG_negative>=PMG_SET_POINT
        # 14) PESS_DC-PESS_C-SOC_positve<=PESS_SET_POINT
        # 15) PESS_DC-PESS_C+SOC_negative>=PESS_SET_POINT
        # 1）
        Aineq = zeros(NX)
        bineq = []
        Aineq[PG] = 1
        Aineq[RG] = 1
        bineq.append(model["DG"]["PMAX"])
        # 2）
        Aineq_temp = zeros(NX)
        Aineq_temp[PG] = -1
        Aineq_temp[RG] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["DG"]["PMIN"])
        # 3）
        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = 1
        Aineq_temp[RUG] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["UG"]["PMAX"])
        # 4）
        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = -1
        Aineq_temp[RUG] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["UG"]["PMIN"])
        # 5）
        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = 1
        Aineq_temp[PESS_C] = -1
        Aineq_temp[RESS] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["PMAX_DIS"])
        # 6）
        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = -1
        Aineq_temp[PESS_C] = 1
        Aineq_temp[RESS] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["PMAX_CH"])
        # 7）
        Aineq_temp = zeros(NX)
        Aineq_temp[EESS] = -1
        Aineq_temp[RESS] = configuration_time_line.default_time["Time_step_opf"] / 3600
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"])
        # 8）
        Aineq_temp = zeros(NX)
        Aineq_temp[EESS] = 1
        Aineq_temp[RESS] = configuration_time_line.default_time["Time_step_opf"] / 3600
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"])
        # 9）
        # No reserve requirement

        # 10）
        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = 1
        Aineq_temp[PUG_positive] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["UG"]["COMMAND_PG"])
        # 11）
        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = -1
        Aineq_temp[PUG_negative] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["UG"]["COMMAND_PG"])
        # 12）
        Aineq_temp = zeros(NX)
        Aineq_temp[PMG] = 1
        Aineq_temp[PMG_positive] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["PMG"])
        # 13）
        Aineq_temp = zeros(NX)
        Aineq_temp[PMG] = -1
        Aineq_temp[PMG_negative] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["PMG"])
        # 14）
        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = 1
        Aineq_temp[PESS_C] = -1
        Aineq_temp[SOC_positive] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["COMMAND_PG"])
        # 15）
        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = -1
        Aineq_temp[PESS_C] = 1
        Aineq_temp[SOC_negative] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["ESS"]["COMMAND_PG"])

        c = zeros(NX)
        c[PG] = model["DG"]["COST"][0]
        c[PUG] = model["UG"]["COST"][0]
        c[PESS_C] = model["ESS"]["COST_CH"][0]
        c[PESS_DC] = model["ESS"]["COST_DIS"][0]
        # Add the constraints to the local optimal power flow
        c[PMG_negative] = configuration_eps.default_eps["Penalty_opf"]
        c[PMG_positive] = configuration_eps.default_eps["Penalty_opf"]
        c[PUG_positive] = configuration_eps.default_eps["Penalty_opf"]
        c[PUG_negative] = configuration_eps.default_eps["Penalty_opf"]
        c[SOC_positive] = configuration_eps.default_eps["Penalty_opf"]
        c[SOC_negative] = configuration_eps.default_eps["Penalty_opf"]
        c[PBIC_AC2DC] = configuration_eps.default_eps[
                            "Penalty_opf"] / 10  # These two items are added to remove the bilinear constraints :1)
        c[PBIC_DC2AC] = configuration_eps.default_eps["Penalty_opf"] / 10  # 2)
        # Return the mathematical models
        mathematical_model = {"c": c,
                              "Aeq": Aeq,
                              "beq": beq,
                              "A": Aineq,
                              "b": bineq,
                              "lb": lb,
                              "ub": ub}

        return mathematical_model

    def problem_formulation_local_recovery(*args):
        from configuration import configuration_time_line
        from modelling.power_flow.idx_opf_set_points_tracing_recovery import PG, QG, RG, PUG, QUG, RUG, PBIC_AC2DC, \
            PBIC_DC2AC, QBIC, \
            PESS_C, PESS_DC, RESS, EESS, PMG, PPV, PWP, PL_AC, PL_UAC, PL_DC, PL_UDC, PMG_negative, PMG_positive, \
            PUG_negative, PUG_positive, SOC_negative, SOC_positive, NX

        model = args[0]  # If multiple models are inputed, more local ems models will be formulated
        ## The infeasible optimal problem formulation
        lb = zeros(NX)
        ub = zeros(NX)
        ## Update lower boundary
        lb[PG] = model["DG"]["PMIN"]
        lb[QG] = model["DG"]["QMIN"]
        lb[RG] = model["DG"]["PMIN"]

        lb[PUG] = model["UG"]["PMIN"]
        lb[QUG] = model["UG"]["QMIN"]
        lb[RUG] = model["UG"]["PMIN"]

        lb[PBIC_AC2DC] = 0
        lb[PBIC_DC2AC] = 0
        lb[QBIC] = -model["BIC"]["CAP"]

        lb[PESS_C] = 0
        lb[PESS_DC] = 0
        lb[RESS] = 0
        lb[EESS] = model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"]

        lb[PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line
        lb[PPV] = 0
        lb[PWP] = 0
        lb[PL_AC] = 0
        lb[PL_UAC] = 0
        lb[PL_DC] = 0
        lb[PL_UDC] = 0

        lb[PMG_negative] = 0
        lb[PMG_positive] = 0
        lb[PUG_positive] = 0
        lb[PUG_negative] = 0
        lb[SOC_positive] = 0
        lb[SOC_negative] = 0

        ## Update lower boundary
        ub[PG] = model["DG"]["PMAX"]
        ub[QG] = model["DG"]["QMAX"]
        ub[RG] = model["DG"]["PMAX"]

        ub[PUG] = model["UG"]["PMAX"]
        ub[QUG] = model["UG"]["QMAX"]
        ub[RUG] = model["UG"]["PMAX"]

        ub[PBIC_AC2DC] = model["BIC"]["CAP"]
        ub[PBIC_DC2AC] = model["BIC"]["CAP"]
        ub[QBIC] = model["BIC"]["CAP"]

        ub[PESS_C] = model["ESS"]["PMAX_CH"]
        ub[PESS_DC] = model["ESS"]["PMAX_DIS"]
        ub[RESS] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]
        ub[EESS] = model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"]

        ub[PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line

        ub[PPV] = model["PV"]["PG"]
        ub[PWP] = model["WP"]["PG"]
        ub[PL_AC] = model["Load_ac"]["PD"]
        ub[PL_UAC] = model["Load_uac"]["PD"]
        ub[PL_DC] = model["Load_dc"]["PD"]
        ub[PL_UDC] = model["Load_udc"]["PD"]

        ub[PMG_positive] = 0  # This boundary information will ne updated to the
        ub[PMG_negative] = 0
        ub[PUG_positive] = model["UG"]["PMAX"]
        ub[PUG_negative] = model["UG"]["PMAX"]
        ub[SOC_positive] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]  # The up relaxation of SOC, this is
        ub[SOC_negative] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]  # The up relaxation of SOC
        ## Constraints set
        # 1) Power balance equation
        Aeq = zeros(NX)
        beq = []
        Aeq[PG] = 1
        Aeq[PUG] = 1
        Aeq[PBIC_AC2DC] = -1
        Aeq[PBIC_DC2AC] = model["BIC"]["EFF_DC2AC"]
        Aeq[PL_AC] = -1
        Aeq[PL_UAC] = -1
        beq.append(0)
        # 2) DC power balance equation
        Aeq_temp = zeros(NX)
        Aeq_temp[PBIC_AC2DC] = model["BIC"]["EFF_AC2DC"]
        Aeq_temp[PBIC_DC2AC] = -1
        Aeq_temp[PESS_C] = -1
        Aeq_temp[PESS_DC] = 1
        Aeq_temp[PMG] = -1
        Aeq_temp[PL_DC] = -1
        Aeq_temp[PL_UDC] = -1
        Aeq_temp[PPV] = 1
        Aeq_temp[PWP] = 1
        Aeq = vstack([Aeq, Aeq_temp])
        beq.append(0)
        # 3) Reactive power balance equation
        Aeq_temp = zeros(NX)
        Aeq_temp[QG] = 1
        Aeq_temp[QUG] = 1
        Aeq_temp[QBIC] = 1
        Aeq = vstack([Aeq, Aeq_temp])
        beq.append(model["Load_ac"]["QD"] + model["Load_uac"]["QD"])
        # 4) Energy storage system
        Aeq_temp = zeros(NX)
        Aeq_temp[EESS] = 1
        Aeq_temp[PESS_C] = -model["ESS"]["EFF_CH"] * configuration_time_line.default_time["Time_step_opf"] / 3600
        Aeq_temp[PESS_DC] = 1 / model["ESS"]["EFF_DIS"] * configuration_time_line.default_time[
            "Time_step_opf"] / 3600
        Aeq = vstack([Aeq, Aeq_temp])
        beq.append(model["ESS"]["SOC"] * model["ESS"]["CAP"])

        # Inequality constraints
        # 1) PG + RG <= PGMAX
        # 2) PG - RG >= PGMIN
        # 3) PUG + RUG <= PUGMAX
        # 4) PUG - RUG >= PUGMIN
        # 5) PESS_DC - PESS_C + RESS <= PESS_DC_MAX
        # 6) PESS_DC - PESS_C - RESS >= -PESS_C_MAX
        # 7) EESS - RESS*delta >= EESSMIN
        # 8) EESS + RESS*delta <= EESSMAX
        # 9) RG + RUG + RESS >= sum(Load)*beta + sum(PV)*beta_pv + sum(WP)*beta_wp

        Aineq = zeros(NX)
        bineq = []
        Aineq[PG] = 1
        Aineq[RG] = 1
        bineq.append(model["DG"]["PMAX"])

        Aineq_temp = zeros(NX)
        Aineq_temp[PG] = -1
        Aineq_temp[RG] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["DG"]["PMIN"])

        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = 1
        Aineq_temp[RUG] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["UG"]["PMAX"])

        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = -1
        Aineq_temp[RUG] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["UG"]["PMIN"])

        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = 1
        Aineq_temp[PESS_C] = -1
        Aineq_temp[RESS] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["PMAX_DIS"])

        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = -1
        Aineq_temp[PESS_C] = 1
        Aineq_temp[RESS] = 1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["PMAX_CH"])

        Aineq_temp = zeros(NX)
        Aineq_temp[EESS] = -1
        Aineq_temp[RESS] = configuration_time_line.default_time["Time_step_opf"] / 3600
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"])

        Aineq_temp = zeros(NX)
        Aineq_temp[EESS] = 1
        Aineq_temp[RESS] = configuration_time_line.default_time["Time_step_opf"] / 3600
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"])

        # 10）
        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = 1
        Aineq_temp[PUG_positive] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["UG"]["COMMAND_PG"])
        # 11）
        Aineq_temp = zeros(NX)
        Aineq_temp[PUG] = -1
        Aineq_temp[PUG_negative] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["UG"]["COMMAND_PG"])
        # 12）
        Aineq_temp = zeros(NX)
        Aineq_temp[PMG] = 1
        Aineq_temp[PMG_positive] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["PMG"])
        # 13）
        Aineq_temp = zeros(NX)
        Aineq_temp[PMG] = -1
        Aineq_temp[PMG_negative] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["PMG"])
        # 14）
        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = 1
        Aineq_temp[PESS_C] = -1
        Aineq_temp[SOC_positive] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(model["ESS"]["COMMAND_PG"])
        # 15）
        Aineq_temp = zeros(NX)
        Aineq_temp[PESS_DC] = -1
        Aineq_temp[PESS_C] = 1
        Aineq_temp[SOC_negative] = -1
        Aineq = vstack([Aineq, Aineq_temp])
        bineq.append(-model["ESS"]["COMMAND_PG"])

        # No reserve requirement
        c = zeros(NX)
        c[PG] = model["DG"]["COST"][0]
        c[PUG] = model["UG"]["COST"][0]
        c[PESS_C] = model["ESS"]["COST_CH"][0]
        c[PESS_DC] = model["ESS"]["COST_DIS"][0]
        # The sheding cost
        c[PPV] = -model["PV"]["COST"]
        c[PWP] = -model["WP"]["COST"]
        c[PL_AC] = -model["Load_ac"]["COST"][0]
        c[PL_UAC] = -model["Load_uac"]["COST"][0]
        c[PL_DC] = -model["Load_dc"]["COST"][0]
        c[PL_UDC] = -model["Load_udc"]["COST"][0]

        # Add the constraints to the local optimal power flow
        c[PMG_negative] = configuration_eps.default_eps["Penalty_opf"]
        c[PMG_positive] = configuration_eps.default_eps["Penalty_opf"]
        c[PUG_positive] = configuration_eps.default_eps["Penalty_opf"]
        c[PUG_negative] = configuration_eps.default_eps["Penalty_opf"]
        c[SOC_positive] = configuration_eps.default_eps["Penalty_opf"]
        c[SOC_negative] = configuration_eps.default_eps["Penalty_opf"]
        c[PBIC_AC2DC] = configuration_eps.default_eps[
                            "Penalty_opf"] / 10  # These two items are added to remove the bilinear constraints :1)
        c[PBIC_DC2AC] = configuration_eps.default_eps["Penalty_opf"] / 10  # 2)

        mathematical_model = {"c": c,
                              "Aeq": Aeq,
                              "beq": beq,
                              "A": Aineq,
                              "b": bineq,
                              "lb": lb,
                              "ub": ub}

        return mathematical_model

    def problem_formulation_universal(*args):
        # Formulate mathematical models for different operations
        local_model = args[0]
        universal_model = args[1]
        type = args[len(args) - 1]  # The last one is the type

        ## Formulating the universal energy models
        if type == "Feasible":
            from modelling.power_flow.idx_opf_set_points_tracing import PMG, NX
            local_model_mathematical = problem_formulation_set_points_tracing.problem_formulation_local(local_model)
            universal_model_mathematical = problem_formulation_set_points_tracing.problem_formulation_local(
                universal_model)
        else:
            from modelling.power_flow.idx_opf_set_points_tracing_recovery import PMG, NX
            local_model_mathematical = problem_formulation_set_points_tracing.problem_formulation_local_recovery(
                local_model)
            universal_model_mathematical = problem_formulation_set_points_tracing.problem_formulation_local_recovery(
                universal_model)
        # Modify the boundary information
        local_model_mathematical["lb"][PMG] = -universal_model["LINE"]["STATUS"] * universal_model["LINE"]["RATE_A"]
        local_model_mathematical["ub"][PMG] = universal_model["LINE"]["STATUS"] * universal_model["LINE"]["RATE_A"]
        universal_model_mathematical["lb"][PMG] = -universal_model["LINE"]["STATUS"] * universal_model["LINE"]["RATE_A"]
        universal_model_mathematical["ub"][PMG] = universal_model["LINE"]["STATUS"] * universal_model["LINE"]["RATE_A"]
        ## Modify the matrix
        neq = local_model_mathematical["Aeq"].shape[0]  # Number of equality constraint
        nineq = local_model_mathematical["A"].shape[0]  # Number of inequality constraint
        Aeq_compact = zeros((2 * neq, 2 * NX))
        beq_compact = zeros(2 * neq)
        Aineq_compact = zeros((2 * nineq, 2 * NX))
        bineq_compact = zeros(2 * nineq)
        c_compact = zeros(2 * NX)

        Aeq_compact[0:neq, 0:NX] = local_model_mathematical["Aeq"]
        Aeq_compact[neq:2 * neq, NX:2 * NX] = universal_model_mathematical["Aeq"]
        beq_compact[0: neq] = local_model_mathematical["beq"]
        beq_compact[neq: 2 * neq] = universal_model_mathematical["beq"]

        Aineq_compact[0:nineq, 0:NX] = local_model_mathematical["A"]
        Aineq_compact[nineq:2 * nineq, NX:2 * NX] = universal_model_mathematical["A"]
        bineq_compact[0:nineq] = local_model_mathematical["b"]
        bineq_compact[nineq:2 * nineq] = universal_model_mathematical["b"]

        c_compact[0:NX] = local_model_mathematical["c"]
        c_compact[NX:2 * NX] = universal_model_mathematical["c"]
        c_compact = array(c_compact)

        lb = numpy.append(local_model_mathematical["lb"], universal_model_mathematical["lb"])
        ub = numpy.append(local_model_mathematical["ub"], universal_model_mathematical["ub"])

        Aeq_compact_temp = zeros(2 * NX)
        Aeq_compact_temp[PMG] = 1
        Aeq_compact_temp[NX + PMG] = 1
        Aeq_compact = vstack([Aeq_compact, Aeq_compact_temp])
        beq_compact = numpy.append(beq_compact, zeros(1))

        model = {"c": c_compact,
                 "Aeq": Aeq_compact,
                 "beq": beq_compact,
                 "A": Aineq_compact,
                 "b": bineq_compact,
                 "lb": lb,
                 "ub": ub}
        return model
    # There is no need to update the universal energy management system
