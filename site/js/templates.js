/**
 * MythicBee — Template System
 * Pre-made layouts for different gift types
 */

const TEMPLATES = {
  newspaper: {
    id: "newspaper",
    name: "The Times",
    description: "A very serious newspaper about a deeply unserious subject.",
    price: 24,
    category: "print",
    layout: "newspaper",
    fields: {
      headline: { label: "Headline", type: "text", placeholder: "LOCAL MAN MAKES HISTORY", auto: true },
      subhead: { label: "Subheading", type: "text", placeholder: "Family sources confirm he's always been like this", auto: true },
      body: { label: "Main story", type: "textarea", placeholder: "In a stunning turn of events...", auto: true },
      quote: { label: "Famous quote", type: "text", placeholder: '"He once ate an entire cake in one sitting"', auto: true },
      photo: { label: "Photo", type: "image", required: true },
    },
    preview: {
      bg: "#f5f0e8",
      headerBg: "#1a1a2e",
      headerColor: "#f5f0e8",
      fontFamily: "'Playfair Display', serif",
      bodyFont: "'Georgia', serif",
    }
  },
  biography: {
    id: "biography",
    name: "The Biography",
    description: "An unauthorized account of a life well-lived.",
    price: 29,
    category: "print",
    layout: "biography",
    fields: {
      name: { label: "Their name", type: "text", placeholder: "David Thompson", auto: true },
      title: { label: "Book title", type: "text", placeholder: "The Extraordinary Life of...", auto: true },
      chapter1: { label: "Chapter 1: Early years", type: "textarea", placeholder: "Born in a small town...", auto: true },
      chapter2: { label: "Chapter 2: The adventure", type: "textarea", placeholder: "Nobody expected what happened next...", auto: true },
      chapter3: { label: "Chapter 3: Legacy", type: "textarea", placeholder: "What they'll remember most...", auto: true },
      photo: { label: "Cover photo", type: "image", required: true },
    },
    preview: {
      bg: "#faf8f5",
      accent: "#8b6914",
      fontFamily: "'Playfair Display', serif",
      bodyFont: "'Georgia', serif",
    }
  },
  story: {
    id: "story",
    name: "The Story",
    description: "A picture book of memories, moments, and meaning.",
    price: 34,
    category: "print",
    layout: "storybook",
    fields: {
      title: { label: "Book title", type: "text", placeholder: "The Day Everything Changed", auto: true },
      page1: { label: "Page 1", type: "textarea", placeholder: "Once upon a time...", auto: true },
      page2: { label: "Page 2", type: "textarea", placeholder: "And then one day...", auto: true },
      page3: { label: "Page 3", type: "textarea", placeholder: "From that moment on...", auto: true },
      photos: { label: "Photos", type: "image-multiple", max: 3 },
    },
    preview: {
      bg: "#fffef9",
      accent: "#d4af37",
      fontFamily: "'Playfair Display', serif",
      bodyFont: "'Georgia', serif",
    }
  },
  poster: {
    id: "poster",
    name: "The Poster",
    description: "A stunning print for their wall.",
    price: 19,
    category: "print",
    layout: "poster",
    fields: {
      headline: { label: "Main text", type: "text", placeholder: "LEGEND", auto: true },
      subtext: { label: "Subtext", type: "text", placeholder: "Since 1964", auto: true },
      photo: { label: "Photo", type: "image", required: true },
    },
    preview: {
      bg: "#1a1a2e",
      accent: "#d4af37",
      fontFamily: "'Playfair Display', serif",
      bodyFont: "'Georgia', serif",
    }
  },
  card: {
    id: "card",
    name: "The Card",
    description: "With a little something inside.",
    price: 12,
    category: "print",
    layout: "card",
    fields: {
      message: { label: "Your message", type: "textarea", placeholder: "To someone who makes every day better...", auto: true },
      from: { label: "From", type: "text", placeholder: "With love", auto: true },
      photo: { label: "Photo", type: "image" },
    },
    preview: {
      bg: "#fffef9",
      accent: "#d4af37",
      fontFamily: "'Playfair Display', serif",
      bodyFont: "'Georgia', serif",
    }
  }
};

/**
 * Auto-fill template fields from GiftBrief
 */
function autoFillFromBrief(template, brief) {
  const filled = {};
  const name = brief.recipient || "them";
  const relationship = brief.relationship || "";
  const interests = brief.interests || [];
  const personality = brief.personality || "";
  const occasion = brief.occasion || "special day";
  const age = brief.age || "";

  switch (template.id) {
    case "newspaper":
      filled.headline = generateHeadline(name, occasion, interests);
      filled.subhead = generateSubhead(name, personality, interests);
      filled.body = generateBody(name, relationship, interests, personality);
      filled.quote = generateQuote(name, personality);
      break;
    case "biography":
      filled.name = name;
      filled.title = `The Extraordinary Life of ${name}`;
      filled.chapter1 = generateChapter1(name, age, relationship);
      filled.chapter2 = generateChapter2(name, interests, personality);
      filled.chapter3 = generateChapter3(name, relationship);
      break;
    case "story":
      filled.title = `${name}'s Story`;
      filled.page1 = generateStoryPage1(name, relationship);
      filled.page2 = generateStoryPage2(name, interests);
      filled.page3 = generateStoryPage3(name, relationship);
      break;
    case "poster":
      filled.headline = name.toUpperCase();
      filled.subtext = age ? `Since ${new Date().getFullYear() - age}` : "A Living Legend";
      break;
    case "card":
      filled.message = `To ${name},\n\nYou make every day better just by being you.`;
      filled.from = "With love";
      break;
  }
  return filled;
}

function generateHeadline(name, occasion, interests) {
  const headlines = [
    `${name.toUpperCase()} DECLARES ${occasion ? occasion.toUpperCase() : "SPECIAL DAY"}`,
    `LOCAL ${interests[0] ? interests[0].toUpperCase() : "LEGEND"} MAKES HISTORY`,
    `${name.toUpperCase()} CELEBRATES ${occasion ? occasion.toUpperCase() : "EVERYTHING"}`,
    `BREAKING: ${name.toUpperCase()} STILL ABSOLUTELY BRILLIANT`
  ];
  return headlines[Math.floor(Math.random() * headlines.length)];
}

function generateSubhead(name, personality, interests) {
  return `Family sources confirm ${name} has always been like this`;
}

function generateBody(name, relationship, interests, personality) {
  let body = `In a stunning development, ${name} has once again proven to be`;
  if (personality) body += ` ${personality}`;
  body += `.\n\n`;
  if (interests.length > 0) {
    body += `Known for their passionate love of ${interests.join(" and ")}, `;
  }
  body += `${name} continues to inspire those around them.`;
  return body;
}

function generateQuote(name, personality) {
  return `"${name} once said something so profound we had to put it on a newspaper."`;
}

function generateChapter1(name, age, relationship) {
  return `Born  years ago, ${name} showed early signs of being absolutely extraordinary. As a ${relationship || "child"}, they displayed a rare combination of ${age > 40 ? "wisdom" : "energy"} and ${Math.random() > 0.5 ? "humor" : "kindness"}.`;
}

function generateChapter2(name, interests, personality) {
  let chapter = `The middle years were where ${name} truly came into their own.`;
  if (interests.length > 0) {
    chapter += ` Their passion for ${interests[0]} became legendary.`;
  }
  if (personality) {
    chapter += ` Their ${personality} nature made them beloved by all.`;
  }
  return chapter;
}

function generateChapter3(name, relationship) {
  return `${name}'s legacy is simple: they made everyone around them feel like they mattered. That's the kind of ${relationship || "person"} the world needs more of.`;
}

function generateStoryPage1(name, relationship) {
  return `Once upon a time, there was a ${relationship || "person"} named ${name}. And they were absolutely wonderful.`;
}

function generateStoryPage2(name, interests) {
  let page = `Every day with ${name} was an adventure.`;
  if (interests.length > 0) {
    page += ` They loved ${interests.join(", ")} more than anything.`;
  }
  return page;
}

function generateStoryPage3(name, relationship) {
  return `And so ${name} lived happily ever after, making the world a better place just by being in it. The End.`;
}

export { TEMPLATES, autoFillFromBrief };
