# Mobile App Waitlist

Join the waitlist to be notified when the Elroy mobile app becomes available!

<div id="waitlist-form">
    <form id="waitlist-signup" style="max-width: 500px; padding: 20px 0;">
        <div style="margin-bottom: 15px;">
            <label for="email" style="display: block; margin-bottom: 5px; font-weight: bold;">Email Address *</label>
            <input type="email" id="email" name="email" required
                   style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px;">
        </div>

        <div style="margin-bottom: 15px;">
            <label for="use_case" style="display: block; margin-bottom: 5px; font-weight: bold;">What would you like to do with a memory assistant mobile app?</label>
            <textarea id="use_case" name="use_case" rows="4"
                      placeholder="e.g., Remember important conversations, track daily insights, manage reminders..."
                      style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; resize: vertical;"></textarea>
        </div>

        <div style="margin-bottom: 20px;">
            <label for="platform" style="display: block; margin-bottom: 5px; font-weight: bold;">Preferred Mobile Platform</label>
            <select id="platform" name="platform"
                    style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px;">
                <option value="">Select platform (optional)</option>
                <option value="iOS">iOS</option>
                <option value="Android">Android</option>
                <option value="Both">Both iOS and Android</option>
            </select>
        </div>

        <button type="submit"
                style="width: 100%; padding: 12px; background-color: #B4B0CC; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer;">
            Join Waitlist
        </button>

        <div id="form-message" style="margin-top: 15px; padding: 10px; border-radius: 4px; display: none;"></div>
    </form>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('waitlist-signup');
    const messageDiv = document.getElementById('form-message');

    // Get API base URL from MkDocs config
    const apiBaseUrl = '{{ config.extra.api_base_url }}';

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData(form);
        const data = {
            email: formData.get('email'),
            use_case: formData.get('use_case'),
            platform: formData.get('platform') || null
        };

        try {
            // Disable submit button
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Submitting...';

            const response = await fetch(`${apiBaseUrl}/waitlist`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                messageDiv.style.display = 'block';
                messageDiv.style.backgroundColor = '#d4edda';
                messageDiv.style.color = '#155724';
                messageDiv.style.border = '1px solid #c3e6cb';
                messageDiv.textContent = result.message;
                form.reset();
            } else {
                throw new Error(result.message || 'Failed to join waitlist');
            }
        } catch (error) {
            messageDiv.style.display = 'block';
            messageDiv.style.backgroundColor = '#f8d7da';
            messageDiv.style.color = '#721c24';
            messageDiv.style.border = '1px solid #f5c6cb';
            messageDiv.textContent = 'Error: ' + error.message;
        } finally {
            // Re-enable submit button
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.disabled = false;
            submitButton.textContent = 'Join Waitlist';
        }
    });
});
</script>

Stay tuned for updates!
