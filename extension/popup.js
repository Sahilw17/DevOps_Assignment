document.addEventListener("DOMContentLoaded", async () => {
  const urlInput = document.getElementById("server-url");
  const saveBtn = document.getElementById("save-btn");
  const savedMsg = document.getElementById("saved-msg");
  const statusBadge = document.getElementById("conn-status");

  // Load saved settings
  const result = await chrome.storage.local.get(["serverUrl"]);
  if (result.serverUrl) {
    urlInput.value = result.serverUrl;
  }

  // Check socket connectivity briefly
  checkConnection(urlInput.value);

  saveBtn.addEventListener("click", async () => {
    const newUrl = urlInput.value.trim();
    if (!newUrl) return;

    await chrome.storage.local.set({ serverUrl: newUrl });
    savedMsg.style.display = "block";
    checkConnection(newUrl);

    setTimeout(() => {
      savedMsg.style.display = "none";
    }, 2000);
  });

  function checkConnection(url) {
    try {
      const testWs = new WebSocket(url);
      testWs.onopen = () => {
        statusBadge.textContent = "Online";
        statusBadge.className = "badge badge-online";
        testWs.close();
      };
      testWs.onerror = () => {
        statusBadge.textContent = "Offline";
        statusBadge.className = "badge badge-offline";
      };
    } catch (e) {
      statusBadge.textContent = "Offline";
      statusBadge.className = "badge badge-offline";
    }
  }
});
