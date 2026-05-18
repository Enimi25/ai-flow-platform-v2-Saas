<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI FLOW Content Factory</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>
*{margin:0;padding:0;box-sizing:border-box}

body{
  background:#050816;
  color:white;
  font-family:Arial,sans-serif;
  display:flex;
  min-height:100vh;
}

.sidebar{
  width:260px;
  background:#0b1023;
  border-right:1px solid rgba(255,255,255,.08);
  padding:30px 20px;
}

.logo{
  font-size:28px;
  font-weight:900;
  margin-bottom:50px;
}

.logo span{color:#4ade80}

.menu{
  display:flex;
  flex-direction:column;
  gap:14px;
}

.menu a{
  text-decoration:none;
  color:#cbd5e1;
  padding:14px 18px;
  border-radius:14px;
}

.menu a:hover{background:#111936;color:white}

.menu .active{
  background:#4ade80;
  color:#020617;
  font-weight:900;
}

.main{
  flex:1;
  padding:40px;
}

.top{
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:35px;
}

h1{
  font-size:36px;
  margin-bottom:8px;
}

.sub{
  color:#94a3b8;
}

.user{
  display:flex;
  align-items:center;
  gap:12px;
}

.logout{
  background:#1e293b;
  color:white;
  border:1px solid rgba(255,255,255,.1);
  border-radius:12px;
  padding:10px 14px;
  cursor:pointer;
  font-weight:800;
}

.actions{
  display:flex;
  gap:12px;
  margin-bottom:22px;
  flex-wrap:wrap;
}

button{
  border:0;
  border-radius:12px;
  padding:12px 16px;
  font-weight:900;
  cursor:pointer;
}

.green{
  background:#4ade80;
  color:#020617;
}

.dark{
  background:#1e293b;
  color:white;
  border:1px solid rgba(255,255,255,.1);
}

.grid{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:24px;
}

.card{
  background:#0f172a;
  border:1px solid rgba(255,255,255,.06);
  border-radius:24px;
  padding:24px;
}

.card h2{
  font-size:24px;
  margin-bottom:18px;
}

label{
  display:block;
  color:#94a3b8;
  font-size:14px;
  margin-bottom:8px;
}

input, select, textarea{
  width:100%;
  background:#020617;
  color:white;
  border:1px solid rgba(255,255,255,.1);
  border-radius:14px;
  padding:14px;
  margin-bottom:16px;
  outline:none;
}

textarea{
  min-height:120px;
  resize:vertical;
}

.post{
  background:#111936;
  border:1px solid rgba(255,255,255,.06);
  border-radius:18px;
  padding:18px;
  margin-bottom:14px;
}

.post h3{
  margin-bottom:8px;
}

.post p{
  color:#cbd5e1;
  line-height:1.5;
  font-size:14px;
}

.meta{
  margin-top:12px;
  color:#4ade80;
  font-size:12px;
  font-weight:900;
}

.msg{
  color:#94a3b8;
  margin-bottom:16px;
}

.empty{
  color:#94a3b8;
  line-height:1.5;
}

@media(max-width:900px){
  body{display:block}
  .sidebar{width:100%}
  .grid{grid-template-columns:1fr}
}
</style>
</head>

<body>

<div class="sidebar">
  <div class="logo">AI <span>FLOW</span></div>

  <div class="menu">
    <a href="/dashboard">Dashboard</a>
    <a href="/leads-page">Leads</a>
    <a href="/content-factory" class="active">Content Factory</a>
    <a href="/dashboard">Social Accounts</a>
    <a href="/dashboard">AI Replies</a>
    <a href="/dashboard">Analytics</a>
    <a href="/dashboard">Calendar</a>
    <a href="/dashboard">Billing</a>
    <a href="/dashboard">Settings</a>
  </div>
</div>

<div class="main">

  <div class="top">
    <div>
      <h1>Content Factory</h1>
      <div class="sub">Generate and manage social posts for this client.</div>
    </div>

    <div class="user">
      <div id="clientEmail">Client</div>
      <button class="logout" onclick="logout()">Logout</button>
    </div>
  </div>

  <div class="actions">
    <button class="green" onclick="generatePost()">Generate AI Post</button>
    <button class="dark" onclick="loadPosts()">Refresh Posts</button>
    <button class="dark" onclick="goDashboard()">Back to Dashboard</button>
  </div>

  <div id="msg" class="msg">Loading...</div>

  <div class="grid">

    <div class="card">
      <h2>Create New Post</h2>

      <label>Platform</label>
      <select id="platform">
        <option>Instagram</option>
        <option>Facebook</option>
        <option>TikTok</option>
        <option>LinkedIn</option>
      </select>

      <label>Post Type</label>
      <select id="postType">
        <option>caption</option>
        <option>ad</option>
        <option>reel idea</option>
        <option>story</option>
        <option>carousel</option>
      </select>

      <label>Topic</label>
      <textarea id="topic">AI sales automation for small businesses</textarea>

      <button class="green" onclick="generatePost()">Generate Content</button>
    </div>

    <div class="card">
      <h2>Saved Posts</h2>
      <div id="postsBody">
        <div class="empty">No posts yet.</div>
      </div>
    </div>

  </div>

</div>

<script>
const email = localStorage.getItem("ai_flow_email");
const companyId = localStorage.getItem("ai_flow_company_id");

if (!email || !companyId) {
  window.location.href = "/login";
}

document.getElementById("clientEmail").innerText = email;

function logout(){
  localStorage.removeItem("ai_flow_email");
  localStorage.removeItem("ai_flow_role");
  localStorage.removeItem("ai_flow_company_id");
  window.location.href = "/login";
}

function goDashboard(){
  window.location.href = "/dashboard";
}

function setMsg(text){
  document.getElementById("msg").innerText = text;
}

async function loadPosts(){
  setMsg("Loading posts...");

  try{
    const res = await fetch("/dashboard-data?companyId=" + encodeURIComponent(companyId));
    const data = await res.json();

    if(!res.ok || data.error){
      setMsg(data.error || "Error loading posts.");
      return;
    }

    const posts = data.posts || [];
    const body = document.getElementById("postsBody");
    body.innerHTML = "";

    if(!posts.length){
      body.innerHTML = '<div class="empty">No posts yet.</div>';
      setMsg("No posts yet.");
      return;
    }

    posts.forEach(post => {
      const div = document.createElement("div");
      div.className = "post";

      div.innerHTML = `
        <h3>${post.title || "Untitled Post"}</h3>
        <p>${post.content || ""}</p>
        <div class="meta">${post.platform || ""} · ${post.post_type || ""} · ${post.status || "draft"}</div>
      `;

      body.appendChild(div);
    });

    setMsg("Loaded " + posts.length + " posts.");

  }catch(e){
    setMsg("Connection error.");
  }
}

async function generatePost(){
  const platform = document.getElementById("platform").value;
  const postType = document.getElementById("postType").value;
  const topic = document.getElementById("topic").value.trim();

  setMsg("Generating post...");

  try{
    const res = await fetch("/create-content-post", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        companyId: companyId,
        platform: platform,
        postType: postType,
        topic: topic
      })
    });

    const data = await res.json();

    if(!res.ok || data.error){
      setMsg(data.error || "Error generating post.");
      return;
    }

    setMsg("Post generated.");
    loadPosts();

  }catch(e){
    setMsg("Connection error generating post.");
  }
}

loadPosts();
</script>

</body>
</html>
