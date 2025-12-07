import json
import sys
import gurobipy as gp
from gurobipy import GRB

def assign(data):
    if ("students" not in data) or ("capacities" not in data) or ("options" not in data):
        raise ValueError("Input data doesn't have all information needed.")
    students = data["students"]
    capacities = data["capacities"]
    options = data["options"]
    minimum_capacity = options.get("minTeamSize", 0)
    max_sections_per_team = options.get("maxSectionsPerTeam", 1)
    
    # Get student IDs, their choices, and discussion sections
    student_ids = [student["prefId"] for student in students]
    projects = list(capacities.keys())
    student_choices = {}
    student_sections = {}

    for s in students:
        student_id = s["prefId"]
        choices = []
        for choice in s.get("choices", []):
            project_id = choice["projectId"]
            project_name = choice["projectName"]
            rank = choice["rank"]
            choices.append((project_id, project_name, rank))
        student_choices[student_id] = choices

        sections = []
        if s.get("sectionId") != None:
            sections.append(s.get("sectionId"))
        if s.get("sectionIds") != None:
            sections.extend(s.get("sectionIds"))
        student_sections[student_id] = sections

    sections = {sec for secs in student_sections.values() for sec in secs}

    # LP solver
    solver = gp.Model("project_assignment")
    solver.Params.OutputFlag = 0

    # Decision variables
    # x[(student_id, project_id)] = 1 if student assigned to project, else 0
    x = {}  
    for student_id in student_ids:
        for (project_id, _, _) in student_choices[student_id]:
            x[(student_id, project_id)] = solver.addVar(vtype=GRB.BINARY, name=f"x_{student_id}_{project_id}")

    # u[student_id] = 1 if student is unassigned, else 0
    u = {student_id: solver.addVar(vtype=GRB.BINARY, name=f"u_{student_id}") for student_id in student_ids}

    # y[project_id] = 1 if project is used, else 0
    y = {project_id: solver.addVar(vtype=GRB.BINARY, name=f"y_{project_id}") for project_id in projects}

    # If sections are used, define additional variables
    if len(sections) != 0:
        # w[(student_id, project_id, section)] = 1 if student assigned to project in section, else 0
        w = {}
        for student_id in student_ids:
            secs = student_sections[student_id]
            for (project_id, _, _) in student_choices[student_id]:
                for sec in secs:
                    w[(student_id, project_id, sec)] = solver.addVar(vtype=GRB.BINARY, name=f"w_{student_id}_{project_id}_{sec}")

        # z[(project_id, section)] = 1 if project has students in section, else 0
        z = {}
        for project_id in projects:
            for sec in sections:
                z[(project_id, sec)] = solver.addVar(vtype=GRB.BINARY, name=f"z_{project_id}_{sec}")

    solver.update()

    # Constraints
    # Each student is assigned to exactly one project or unassigned
    for student_id in student_ids:
        solver.addConstr(gp.quicksum((x[(student_id, project_id)] for (project_id, _, _) in student_choices[student_id])) + u[student_id] == 1, name=f"assign_{student_id}")

    # Project capacity constraints
    for project_id in projects:
        solver.addConstr(gp.quicksum((x[(student_id, project_id)] for student_id in student_ids if (student_id, project_id) in x)) 
                         <= capacities[project_id] * y[project_id], name=f"max_capacity_{project_id}")
        
        if minimum_capacity >= capacities[project_id]:
            min_capacity = 0
        else:
            min_capacity = minimum_capacity
        solver.addConstr(gp.quicksum((x[(student_id, project_id)] for student_id in student_ids if (student_id, project_id) in x)) 
                         >= min_capacity * y[project_id], name=f"min_capacity_{project_id}")
        
    # Section constraints if sections are used
    if len(sections) != 0:
        # Link x and w variables s.t. each student assigned to a project is also assigned to only one section for that project
        for student_id in student_ids:
            secs = student_sections[student_id]
            for (project_id, _, _) in student_choices[student_id]:
                solver.addConstr(gp.quicksum((w[(student_id, project_id, sec)] for sec in secs)) == x[(student_id, project_id)], name=f"link_x_w_{student_id}_{project_id}")

        # Link w and z variables s.t. if any student is assigned to a project in a section, that section is used for that project
        for project_id in projects:
            capacity = capacities[project_id]
            for sec in sections:
                # List of student who want this project and are in this section
                students_in_sec_and_want_project = [student_id for student_id in student_ids if (student_id, project_id, sec) in w]
                # If no students in this section want this project, force z[(project_id, sec)] = 0
                if len(students_in_sec_and_want_project) == 0:
                    solver.addConstr(z[(project_id, sec)] == 0, name=f"no_students_z_{project_id}_{sec}")
                    continue
                
                solver.addConstr(gp.quicksum(w[(student_id, project_id, sec)] for student_id in students_in_sec_and_want_project) <= capacity * z[(project_id, sec)], name=f"link_z_{project_id}_{sec}")
                solver.addConstr(z[(project_id, sec)] <= y[project_id], name=f"z_y_{project_id}_{sec}")

        # Limit number of sections per project
        for project_id in projects:
            solver.addConstr(gp.quicksum(z[(project_id, sec)] for sec in sections) <= max_sections_per_team * y[project_id], name=f"max_sections_{project_id}")
        

    # Objective
    # Maximize total preference score
    preference_score = gp.quicksum(
        x[(student_id, project_id)] * (len(student_choices[student_id]) - rank + 1)
        for student_id in student_ids
        for (project_id, _, rank) in student_choices[student_id]
    )

    # Penalize unassigned students heavily
    max_weight = max(len(student_choices[s]) for s in student_ids)
    unassigned_penalty = len(student_ids) * max_weight + 1
    penalty = gp.quicksum(unassigned_penalty * u[s] for s in student_ids)

    solver.setObjective(preference_score - penalty, GRB.MAXIMIZE)

    # Solve
    solver.optimize()

    # If no solution found, return all students as unassigned and give reason
    if solver.Status not in (GRB.OPTIMAL, GRB.SUBOPTIMAL):
        assigned = []
        unassigned = [{
            "prefId": s["prefId"], 
            "buid": s["buid"], 
            "studentName": s["studentName"], 
            "reason": f"ILP infeasible or no solution (status {solver.Status})",} 
            for s in students]
        return {"assigned": assigned, "unassigned": unassigned, "totalCost": None}

    # Extract assignments from solution
    assignments = {"assigned": [], "unassigned": [], "totalCost": solver.ObjVal}

    for student in students:
        assigned_project = False
        student_id = student["prefId"]
        project_id = None
        project_name = None
        rank = None
        for (p_id, proj_name, r) in student_choices[student_id]:
            if x[(student_id, p_id)].X > 0.5:
                assigned_project = True
                project_id = p_id
                project_name = proj_name
                rank = r
                break
        if assigned_project:
            assignments["assigned"].append({
                "prefId": student["prefId"],
                "buid": student["buid"],
                "studentName": student["studentName"],
                "projectId": project_id,
                "projectName": project_name,
                "rank": rank})
        elif u[student_id].X > 0.5:
            assignments["unassigned"].append({
                "prefId": student["prefId"],
                "buid": student["buid"],
                "studentName": student["studentName"],
                "reason": "No available capacity for ranked choices"})
        else:
            assignments["unassigned"].append({
                "prefId": student["prefId"],
                "buid": student["buid"],
                "studentName": student["studentName"],
                "reason": "Inconsistent assignment. Not assigned to a project but not explicitly marked unassigned."})
            
    return assignments

def main():
    data = json.load(sys.stdin)
    assignments = assign(data)
    json.dump(assignments, sys.stdout, indent=2)


if __name__ == "__main__":
    main()