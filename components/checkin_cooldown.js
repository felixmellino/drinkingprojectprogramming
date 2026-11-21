const countdowns = new WeakMap();

export default function ({ parentElement, data, setTriggerValue }) {
    const card = parentElement.querySelector(".gate-card");
    const timer = card.querySelector(".reward-points");
    const detail = card.querySelector(".reward-where");
    timer.setAttribute("role", "timer");
    timer.setAttribute("aria-label", "Time until next check-in");
    card.classList.toggle("checkin-cooldown-with-photo", data.hasPhoto);
    detail.hidden = data.hasPhoto;
    detail.textContent = data.limit;

    // Use elapsed browser time so clock differences don't affect the countdown.
    // Keep the same deadline through unrelated reruns (for example, a GPS update).
    let countdown = countdowns.get(parentElement);
    if (countdown?.deadline !== data.deadline || countdown.expired) {
        countdown = {
            deadline: data.deadline,
            expiresAt: performance.now() + data.remainingMs,
            expired: false,
        };
        countdowns.set(parentElement, countdown);
    }

    let timeout;
    function tick() {
        clearTimeout(timeout);
        const remainingMs = Math.max(0, countdown.expiresAt - performance.now());
        const seconds = Math.ceil(remainingMs / 1000);
        timer.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
        if (seconds === 0) {
            if (!countdown.expired) {
                countdown.expired = true;
                setTriggerValue("expired", true);
            }
        } else {
            timeout = setTimeout(tick, remainingMs - (seconds - 1) * 1000);
        }
    }

    tick();
    document.addEventListener("visibilitychange", tick);
    return () => {
        clearTimeout(timeout);
        document.removeEventListener("visibilitychange", tick);
    };
}
