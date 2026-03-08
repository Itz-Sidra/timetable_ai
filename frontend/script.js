document.getElementById("schedulerForm").addEventListener("submit", function(e){

e.preventDefault()

const data = {

divisions: document.getElementById("divisions").value.split(","),

theoryRooms: document.getElementById("theoryRooms").value.split(","),

labRooms: document.getElementById("labRooms").value.split(","),

subjects: document.getElementById("subjects").value.split(","),

timeslots: document.getElementById("timeslots").value.split(",")

}

console.log(data)

localStorage.setItem("schedulerInput", JSON.stringify(data))

window.location.href="timetable.html"

})