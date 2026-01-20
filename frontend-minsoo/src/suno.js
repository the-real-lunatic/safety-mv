const createTrackCard = (track) => {
  const card = document.createElement("div");
  card.className = "stack-card";
  const title = document.createElement("strong");
  title.textContent = track.title || track.id || "track";
  card.appendChild(title);

  const audioUrl = track.minio_audio_url || track.audio_url;
  if (audioUrl) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = audioUrl;
    audio.preload = "none";
    card.appendChild(audio);

    const link = document.createElement("p");
    link.className = "muted";
    link.textContent = audioUrl;
    card.appendChild(link);
  }

  return card;
};

export const renderSuno = (statusEl, tracksEl, suno) => {
  statusEl.textContent = "";
  tracksEl.textContent = "";

  if (!suno) {
    statusEl.textContent = "pending";
    return;
  }

  const summary = [
    suno.task_id ? `task: ${suno.task_id}` : null,
    suno.status ? `status: ${suno.status}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  statusEl.textContent = summary || "pending";

  if (suno.error) {
    const error = document.createElement("p");
    error.className = "muted";
    error.textContent = `error: ${suno.error}`;
    statusEl.appendChild(error);
  }

  const tracks = suno.public_tracks || suno.tracks || [];
  if (!tracks.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "no tracks yet";
    tracksEl.appendChild(empty);
    return;
  }

  tracks.forEach((track) => {
    tracksEl.appendChild(createTrackCard(track));
  });
};

export const shouldContinueSunoPolling = (job) => {
  if (!job || !job.status) {
    return false;
  }
  if (!job.status.startsWith("media")) {
    return false;
  }
  const status = job.suno?.status;
  if (!status) {
    return true;
  }
  return !["stored", "store_failed", "error"].includes(status);
};
