let serverUrl = "http://127.0.0.1:8000";  // Default value
const urlInput = document.getElementById('server-url');
const urlForm = document.getElementById('url-form');
const videoUrlsInput = document.getElementById("video-urls");
const limit = document.getElementById("limit")
// Initialize the server URL input with the value from localStorage, if available
const savedUrl = localStorage.getItem('serverUrl');
if (savedUrl) {
    serverUrl = savedUrl;
    urlInput.value = serverUrl;
}

// Handle the server URL form submission
urlForm.addEventListener('submit', (event) => {
    event.preventDefault(); // Prevent form from submitting the traditional way
    var newUrl = urlInput.value.trim();
    if (newUrl.endsWith("/")) newUrl=newUrl.slice(0, -1); 
    
    if (newUrl) {
        // Update the global variable
        serverUrl = newUrl;

        // Save URL to localStorage
        localStorage.setItem('serverUrl', serverUrl);
        alert('Server URL saved!');

        // Optionally, you can update other parts of the application that depend on this URL
        // For example, you could refresh or reload parts of your UI
    } else {
        alert('Please enter a valid URL.');
    }
});

// Handle the video form submission
const videoForm = document.getElementById('video-form');
videoForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const videoUrlsText = videoUrlsInput.value.trim();
    let videoUrls = [];
    // Try to parse input as JSON
    try {
        videoUrls = JSON.parse(videoUrlsText);
        // Validate that parsed data is an array of strings
        if (!Array.isArray(videoUrls) || !videoUrls.every(url => typeof url === 'string' && url.trim().length > 0)) {
            throw("Not valid json. Auto treat at text lines")
        }
    }
    catch (err) {
        videoUrls = videoUrlsText.split('\n').map(url => url.trim()).filter(url => url.length > 0);
    }

    if (videoUrls.length > 0) {
        try {
            // Send POST request to the server with video URLs
            const response = await fetch(`${serverUrl}/crawl?limit=` + limit.value, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(videoUrls)
            });

            if (!response.ok) {
                alert('Network response was not ok');
            }

            const result = await response.json();

            if (result)
                alert('Videos are now being crawed!');
            else alert('There may be pending tasks, cannot crawl')
        } catch (error) {
            console.error('Error:', error);
            alert('There was a problem with the request.');
        }

        // Clear the input after processing
        videoUrlsInput.value = '';
    } else {
        alert('Please enter at least one video URL.');
    }
});


let columns = [{
    title: "Video",
    data: "details.title",
    defaultContent: "Pending"
}, {
    title: "Comments",
    data: "_comments",
    defaultContent: "Pending",
    render: function (data, type, row) {
        if (row.hasOwnProperty("comments")) return "Done: " + row.comments;
        return (data == 0 ? "Downloading" : "Downloading " + data)
    }
}, {
    title: "Captions",
    data: "_captions",
    defaultContent: "Pending",
    render: function (data, type, row) {
        if (row.hasOwnProperty("captions")) return "Done: " + row.captions
        return (data == 0 ? "Downloading" : "Downloading " + data)
    }
},
{
    title: "Status",
    data: "status",
    defaultContent: "In progress",
}
]

data = []

var is_fetching = true;


function fetchData() {
    fetch(serverUrl + "/status", {
        method: "GET",
        redirect: 'manual'
    }).then(r => r.json()).then(d => {
        if (Array.isArray(d))
            table.clear().rows.add(d).draw(false);
        setTimeout(fetchData, 2024)
    })
        .catch(err => { console.log(err); setTimeout(fetchData, 1024); })
}



table = $("#myTable").DataTable({ stateSave: true, responsive: true, buttons: ["colvis"], dom: 'Bflpi<t>pl', data, columns, searching: true });
fetchData()

