describe('GramShiksha student journey on the live preview', () => {
  const login = () => {
    cy.visit('/#/login/student');
    cy.get('input[type="email"]').type('student1@gramshiksha.in');
    cy.get('input[type="password"]').type('Learn@1234');
    cy.get('main.container').contains('button', 'Log in').click();
    cy.url().should('include', '#/textbooks');
  };

  it('logs in and loads the student dashboard', () => {
    login();
    cy.contains("Today's Learning").click();
    cy.url().should('include', '#/dashboard');
    cy.contains('Keep learning, keep growing.').should('be.visible');
    cy.contains('Continue Learning').should('be.visible');
    cy.contains('Progress').should('be.visible');
  });

  it('opens a lesson, saves a note, and verifies completion state', () => {
    login();
    cy.contains("Today's Learning").click();
    cy.contains('button', 'Continue').first().click();
    cy.url().should('match', /#\/lesson\/\d+$/);
    cy.get('h1').should('be.visible');
    cy.get('textarea[placeholder="Add note"]').type('Cypress verified lesson note.');
    cy.contains('button', 'Add note').click();
    cy.contains('Cypress verified lesson note.').should('be.visible');
    cy.contains('button', 'Mark complete').then(($button) => {
      if ($button.length) cy.wrap($button).click();
    });
    cy.contains(/Completed|\+10 XP/).should('be.visible');
  });

  it('answers practice questions and shows instant feedback', () => {
    login();
    cy.get('.sidebar-nav').contains('Practice').click();
    cy.url().should('include', '#/practice');
    cy.contains('Question 1 of 10').should('be.visible');
    cy.contains('A. 8').click();
    cy.contains('Completed').should('be.visible');
    cy.contains('button', 'Next').click();
    cy.contains('Question 2 of 10').should('be.visible');
  });

  it('posts a doubt and verifies it in the Q&A feed', () => {
    const question = `Why do plant cells have a cell wall? ${Date.now()}`;
    login();
    cy.contains('Doubts').first().click();
    cy.url().should('include', '#/doubts');
    cy.get('textarea[placeholder*="Type your doubt"]').type(question);
    cy.contains('button', 'Send').click();
    cy.contains(question).should('be.visible');
  });

  it('renders progress analytics and logs out cleanly', () => {
    login();
    cy.contains('Progress').first().click();
    cy.url().should('include', '#/progress');
    cy.contains('Last 14 days').should('be.visible');
    cy.contains('Badges').should('be.visible');
    cy.contains('button', 'Log out').first().click();
    cy.contains('Student login').should('be.visible');
  });
});
