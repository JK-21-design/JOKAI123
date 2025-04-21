// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Handle flash messages
    const flashMessages = document.querySelectorAll('.flash-message');
    if (flashMessages.length > 0) {
        flashMessages.forEach(message => {
            setTimeout(() => {
                message.style.opacity = '0';
                setTimeout(() => {
                    message.remove();
                }, 500);
            }, 5000);
        });
    }

    // Add active class to current navigation item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.main-nav a').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

    // Mobile menu toggle (if needed in the future)
    const menuToggle = document.createElement('button');
    menuToggle.className = 'menu-toggle';
    menuToggle.innerHTML = '☰';
    document.querySelector('.header-container').prepend(menuToggle);

    menuToggle.addEventListener('click', function() {
        document.querySelector('.main-nav').classList.toggle('active');
    });
}); 