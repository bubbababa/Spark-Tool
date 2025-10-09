const projects = [];
function addProject() {
    const input = document.getElementById("project_input");
    const project = input.value.trim();
    if (project === "") return;
    // add to list
    projects.push(project);
    // show in the HTML list
    const list = document.getElementById("project_list");
    const item = document.createElement("li");
    item.textContent = project;
    list.appendChild(item);
    // clear box
    input.value = "";
    // update hidden input with all projects as a comma-separated string
    document.getElementById("projects").value = projects.join(",");
}