function sendValue(value) {
  Streamlit.setComponentValue(value);
}

function clickListener(event) {
  const { offsetX, offsetY } = event;
  const img = document.getElementById("image");
  sendValue({
    x: offsetX,
    y: offsetY,
    width: img.width,
    height: img.height,
    shiftKey: !!event.shiftKey,
    ctrlKey: !!(event.ctrlKey || event.metaKey),
    unix_time: Date.now(),
  });
}

function onRender(event) {
  let { src, use_column_width } = event.detail.args;

  const img = document.getElementById("image");

  if (img.src !== src) {
    img.src = src;
  }

  function resizeImage() {
    img.classList.remove("auto", "fullWidth");
    img.removeAttribute("width");
    img.removeAttribute("height");

    if (use_column_width === "always" || use_column_width === true) {
      img.classList.add("fullWidth");
    } else if (use_column_width === "auto") {
      img.classList.add("auto");
    }

    Streamlit.setFrameHeight(img.height || img.naturalHeight);
  }

  img.onload = resizeImage;
  window.addEventListener("resize", resizeImage);

  img.onmousedown = null;
  img.onclick = clickListener;

  // Suppress browser drag of the image during shift-click range selects.
  img.ondragstart = (e) => e.preventDefault();
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
