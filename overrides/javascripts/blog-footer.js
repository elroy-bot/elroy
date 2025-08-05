// Add footer to blog posts
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a blog post page
    if (window.location.pathname.includes('/blog/') &&
        (window.location.pathname.includes('/posts/') ||
         window.location.pathname.match(/\/blog\/\d{4}\/\d{2}\/\d{2}\//))) {

        // Find the main content area
        const contentArea = document.querySelector('.md-typeset') ||
                           document.querySelector('.md-content__inner') ||
                           document.querySelector('article');

        if (contentArea) {
            // Create the footer element
            const footer = document.createElement('div');
            footer.style.cssText = `
                margin-top: 3rem;
                padding-top: 2rem;
                border-top: 1px solid var(--md-default-fg-color--lightest);
                font-size: 0.9rem;
                color: var(--md-default-fg-color--light);
                text-align: center;
            `;

            footer.innerHTML = `
                <p>
                    I'm an engineering manager and author of
                    <a href="https://github.com/elroy-bot/elroy" target="_blank" rel="noopener">Elroy</a>,
                    an AI memory assistant. <br>Get in touch at
                    <a href="mailto:hello@elroy.bot">hello@elroy.bot</a>
                    or on <a href="https://discord.gg/5PJUY4eMce">Discord</a>
                </p>
            `;

            // Append the footer to the content area
            contentArea.appendChild(footer);
        }
    }
});
