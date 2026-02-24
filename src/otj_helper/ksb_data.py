"""KSB reference data for all supported apprenticeship standards.

ST0787 – Systems Thinking Practitioner L7 (codes: K1–K5, S1–S11, B1–B6)
ST0763 – AI Data Specialist L7         (codes: AK1–AK29, AS1–AS28, AB1–AB6)

The 'A' prefix on ST0763 codes keeps them unique within the single-column
primary key while still sorting and grouping correctly.  The KSB.natural_code
property strips the prefix so the UI always shows the canonical code (K1, S3…).
"""

KSBS = [
    # ─── ST0787 · Systems Thinking Practitioner L7 ────────────────────────────
    # Knowledge
    {
        "code": "K1",
        "spec_code": "ST0787",
        "category": "knowledge",
        "title": "Systems thinking",
        "description": (
            "Understands core systems concepts and laws that underpin and inform "
            "the practical methodologies and methods. Aware of the inter-relationships "
            "between Systems Thinking approaches (including methods and methodologies), "
            "enabling comparisons of paradigms and underpinning philosophies. Understands "
            "provenance of Systems Thinking methodologies and approaches in context of "
            "'schools' of systems thinking and own ontology and epistemology. Understands "
            "essential concepts of systems: complexity, emergence, boundaries, "
            "inter-relationships, multiple-perspectives, randomness, non-linear "
            "relationships, feedback loops, sensitive dependence on initial conditions, "
            "and unpredictability."
        ),
    },
    {
        "code": "K2",
        "spec_code": "ST0787",
        "category": "knowledge",
        "title": "Systems approaches",
        "description": (
            "Has a sound working knowledge of at least three modelling approaches, "
            "as defined in the SCiO professional standard framework, including at least "
            "two of the widely-used systems methodologies or approaches: Critical Systems "
            "Heuristics, Soft Systems Methodology, System Dynamics, Viable Systems Model. "
            "Understands the applicability, benefits and limits of each systems approach "
            "for each situation, and how to integrate them into a broader methodological "
            "design. Understands relevance of, and knows methods for, determining "
            "appropriate scope, scale and systemic levels, for understanding, diagnosing "
            "and modelling situations, or for system design."
        ),
    },
    {
        "code": "K3",
        "spec_code": "ST0787",
        "category": "knowledge",
        "title": "Intervention and engagement",
        "description": (
            "Knows a range of approaches for delivering systems interventions with "
            "differing levels of complexity and ambiguity, including double loop learning, "
            "change methods, and learning cycles."
        ),
    },
    {
        "code": "K4",
        "spec_code": "ST0787",
        "category": "knowledge",
        "title": "Ethics",
        "description": (
            "Working knowledge of ethics as applied to systems interventions generally, "
            "and as applied specifically to sector where practitioner is working. "
            "Appreciates the regulatory environment, and the legal, health and safety "
            "and compliance requirements of the sector the practitioner is working in."
        ),
    },
    {
        "code": "K5",
        "spec_code": "ST0787",
        "category": "knowledge",
        "title": "Assessment and evaluation",
        "description": (
            "Understands a range of quantitative and qualitative assessment and "
            "evaluation methods for determining the outcomes and impact of interventions, "
            "and for evaluating the effectiveness and impact of intervention decisions "
            "and processes."
        ),
    },
    # Skills
    {
        "code": "S1",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Applying systems knowledge",
        "description": (
            "Applies systems laws, concepts and systems thinking approaches in real "
            "world situations, either applied directly, or to support systems "
            "methodologies."
        ),
    },
    {
        "code": "S2",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Approach designs",
        "description": (
            "Recognises the nature of complexity most relevant to the situation of "
            "interest, and selects one or more appropriate approaches from the range "
            "of systems methods or methodologies. Undertakes these across a variety "
            "of domains or sectors. Defines the system of interest, its boundaries, "
            "stakeholders and context. Recognises the benefits or limitations of an "
            "approach; combines or adapts approaches where needed."
        ),
    },
    {
        "code": "S3",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Systems modelling",
        "description": (
            "Develops conceptual models of a variety of systems, real world situations "
            "and scenarios to provide insights into current or future challenges."
        ),
    },
    {
        "code": "S4",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Interpretation",
        "description": (
            "Presents systems models, insights and intervention contributions in a "
            "way that is understandable in the real world."
        ),
    },
    {
        "code": "S5",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Engagement and collaboration",
        "description": (
            "Applies techniques to identify stakeholders and to build and sustain "
            "effective relationships with them. Seeks out and engages with marginalised "
            "viewpoints; counters the dynamics of marginalisation. Collaborates with "
            "and influences diverse stakeholders, colleagues and clients, identifying "
            "and adapting engagement and communication styles. Works effectively as "
            "part of multi-disciplinary groups which have divergent or conflicting "
            "world views. Designs, builds and manages groups to define the desired "
            "outcomes and achieve them."
        ),
    },
    {
        "code": "S6",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Inquiry, information gathering and analysis",
        "description": (
            "Applies a range of inquiry techniques to gather quantitative and "
            "qualitative information, including inputs, transformations, outputs and "
            "outcomes. Defines and designs hard and soft measures. Applies a range of "
            "questioning and listening techniques to enquire with stakeholders, and to "
            "adapt approaches in real time. Uncovers hidden or unstated assumptions, "
            "to evaluate stated assumptions, and to constructively challenge these "
            "where appropriate. Selects, elicits, manages and interprets appropriate "
            "types of data, information and statistics for model building."
        ),
    },
    {
        "code": "S7",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Intervention design",
        "description": (
            "Designs an appropriate intervention strategy for the system of interest, "
            "recognising relevant issues."
        ),
    },
    {
        "code": "S8",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Change implementation",
        "description": (
            "Plans, designs and leads interventions to achieve benefits and learning, "
            "based on sound understanding of a range of change methodologies and "
            "techniques. Uses facilitative processes empathetically to engage "
            "stakeholders in change processes and decision-making. Adapts plans in "
            "response to new data and insights, perspectives and learning."
        ),
    },
    {
        "code": "S9",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Developing self",
        "description": (
            "Applies techniques for structured personal reflexive practice, to monitor "
            "and develop knowledge, skills and self-awareness."
        ),
    },
    {
        "code": "S10",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Leading, communicating and influencing",
        "description": (
            "Educates and influences stakeholders to participate effectively in "
            "challenging and ambiguous situations, including managing confrontation "
            "and conflict constructively."
        ),
    },
    {
        "code": "S11",
        "spec_code": "ST0787",
        "category": "skill",
        "title": "Assessment and evaluation",
        "description": (
            "Develops and implements suitable monitoring and evaluation criteria and "
            "mechanisms, aware of the influence that different system methods can have "
            "in situations."
        ),
    },
    # Behaviours
    {
        "code": "B1",
        "spec_code": "ST0787",
        "category": "behaviour",
        "title": "Develops self and practice",
        "description": (
            "Engages in structured reflection, monitoring and regulating own thought "
            "processes and understanding. Aware of the effect of own and others' biases "
            "and of the mirroring effect of clients' problems."
        ),
    },
    {
        "code": "B2",
        "spec_code": "ST0787",
        "category": "behaviour",
        "title": "Courage and constructive challenge",
        "description": (
            "Prepared to identify and challenge formal and informal centres of power "
            "and authority. Willing to constructively challenge assumptions, norms, "
            "claims and arguments. Adjusts the degree of challenge against political "
            "considerations, to achieve maximum achievable effect with minimum levels "
            "of damage."
        ),
    },
    {
        "code": "B3",
        "spec_code": "ST0787",
        "category": "behaviour",
        "title": "Curious and innovative",
        "description": (
            "Interested in creative solutions; explores areas of ambiguity and "
            "complexity. Seeks innovative solutions and approaches."
        ),
    },
    {
        "code": "B4",
        "spec_code": "ST0787",
        "category": "behaviour",
        "title": "Professional",
        "description": (
            "Seeks to balance the needs of different stakeholders irrespective of "
            "personal bias. Regularly assesses ethical issues in interventions. "
            "Adheres to professional standards."
        ),
    },
    {
        "code": "B5",
        "spec_code": "ST0787",
        "category": "behaviour",
        "title": "Adaptable and cognitively flexible",
        "description": (
            "Enjoys working on ill-defined and/or unbounded problem situations. Is "
            "comfortable with high degrees of uncertainty and with working on a variety "
            "of situations of interest. Accepts change and innovation; actively considers "
            "new approaches to solving problems. Takes an adaptable approach to inquiring, "
            "intervening and stakeholder engagement. Aware of possible unintended "
            "consequences resulting from acting in complex environments."
        ),
    },
    {
        "code": "B6",
        "spec_code": "ST0787",
        "category": "behaviour",
        "title": "Practical",
        "description": (
            "Takes a 'real-world' approach to the application of system models and to "
            "the design of interventions."
        ),
    },

    # ─── ST0763 · AI Data Specialist L7 ───────────────────────────────────────
    # Codes are prefixed 'A' so they are globally unique in the single-column PK.
    # KSB.natural_code strips the prefix for display (AK1 → K1, AS3 → S3, AB2 → B2).
    #
    # Knowledge
    {
        "code": "AK1",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "AI and ML methodologies",
        "description": (
            "How to use AI and machine learning methodologies such as data-mining, "
            "supervised and unsupervised machine learning, natural language processing, "
            "and machine vision to meet business objectives."
        ),
    },
    {
        "code": "AK2",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data storage and ML methods",
        "description": (
            "How to apply modern data storage solutions, processing technologies and "
            "machine learning methods to maximise the impact to the organisation by "
            "drawing conclusions from applied research."
        ),
    },
    {
        "code": "AK3",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Statistical and mathematical methods",
        "description": (
            "How to apply advanced statistical and mathematical methods to commercial "
            "projects."
        ),
    },
    {
        "code": "AK4",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data extraction and linkage",
        "description": (
            "How to extract data from systems and link data from multiple systems to "
            "meet business objectives."
        ),
    },
    {
        "code": "AK5",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data analysis and research techniques",
        "description": (
            "How to design and deploy effective techniques of data analysis and research "
            "to meet the needs of the business and customers."
        ),
    },
    {
        "code": "AK6",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data product delivery",
        "description": (
            "How data products can be delivered to engage the customer, organise "
            "information or solve a business problem using a range of methodologies, "
            "including iterative and incremental development and project management "
            "approaches."
        ),
    },
    {
        "code": "AK7",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Problem solving and solution evaluation",
        "description": (
            "How to solve problems and evaluate software solutions via analysis of "
            "test data and results from research, feasibility, acceptance and usability "
            "testing."
        ),
    },
    {
        "code": "AK8",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Organisational AI policies",
        "description": (
            "How to interpret organisational policies, standards and guidelines in "
            "relation to AI and data."
        ),
    },
    {
        "code": "AK9",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Legal and ethical frameworks",
        "description": (
            "The current or future legal, ethical, professional and regulatory frameworks "
            "which affect the development and launch of AI products."
        ),
    },
    {
        "code": "AK10",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Role and organisational strategy",
        "description": (
            "How own role fits with, and supports, organisational strategy and objectives."
        ),
    },
    {
        "code": "AK11",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "AI and data science impact",
        "description": (
            "The roles and impact of AI, data science and data engineering in industry "
            "and society."
        ),
    },
    {
        "code": "AK12",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Wider social context of AI",
        "description": (
            "The wider social context of AI, data science and related technologies, "
            "to assess business impact of current ethical issues such as workplace "
            "automation and misuse of data."
        ),
    },
    {
        "code": "AK13",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Theory-to-practice trade-offs",
        "description": (
            "How to identify the compromises and trade-offs which must be made when "
            "translating theory into practice in the workplace."
        ),
    },
    {
        "code": "AK14",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Business value of data products",
        "description": (
            "The business value of a data product that can deliver the solution in line "
            "with business needs, quality standards and timescales."
        ),
    },
    {
        "code": "AK15",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data product engineering principles",
        "description": (
            "The engineering principles used (general and software) to investigate and "
            "manage the design, development and deployment of new data products within "
            "the business."
        ),
    },
    {
        "code": "AK16",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "High-performance computing",
        "description": (
            "Understand high-performance computer architectures and how to make "
            "effective use of these."
        ),
    },
    {
        "code": "AK19",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Statistical and ML principles",
        "description": (
            "The principles and properties behind statistical and machine learning "
            "methods."
        ),
    },
    {
        "code": "AK20",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data collection, storage and visualisation",
        "description": (
            "How to collect, store, analyse and visualise data."
        ),
    },
    {
        "code": "AK21",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "AI support for team working",
        "description": (
            "How AI and data science techniques support and enhance the work of other "
            "members of the team."
        ),
    },
    {
        "code": "AK22",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Mathematical principles in AI",
        "description": (
            "The relationship between mathematical principles and core techniques in "
            "AI and data science within the organisational context."
        ),
    },
    {
        "code": "AK23",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Model validation metrics",
        "description": (
            "The use of different performance and accuracy metrics for model validation "
            "in AI projects."
        ),
    },
    {
        "code": "AK24",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Error and bias sources",
        "description": (
            "Sources of error and bias, including how they may be affected by choice "
            "of dataset and methodologies applied."
        ),
    },
    {
        "code": "AK25",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Programming languages and ML libraries",
        "description": (
            "Programming languages and modern machine learning libraries for commercially "
            "beneficial scientific analysis and simulation."
        ),
    },
    {
        "code": "AK26",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Scientific method",
        "description": (
            "The scientific method and its application in research and business contexts, "
            "including experiment design and hypothesis testing."
        ),
    },
    {
        "code": "AK27",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Data collection engineering",
        "description": (
            "The engineering principles used (general and software) to create new "
            "instruments and applications for data collection."
        ),
    },
    {
        "code": "AK28",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Communication of concepts",
        "description": (
            "How to communicate concepts and present in a manner appropriate to diverse "
            "audiences, adapting communication techniques accordingly."
        ),
    },
    {
        "code": "AK29",
        "spec_code": "ST0763",
        "category": "knowledge",
        "title": "Accessibility and diversity",
        "description": (
            "The need for accessibility for all users and diversity of user needs."
        ),
    },
    # Skills
    {
        "code": "AS1",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Data architecture design",
        "description": (
            "Use applied research and data modelling to design and refine the database "
            "and storage architectures to deliver secure, stable and scalable data "
            "products to the business."
        ),
    },
    {
        "code": "AS2",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Test data analysis",
        "description": (
            "Independently analyse test data, interpret results and evaluate the "
            "suitability of proposed solutions, considering current and future business "
            "requirements."
        ),
    },
    {
        "code": "AS3",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Critical evaluation",
        "description": (
            "Critically evaluate arguments, assumptions, abstract concepts and data "
            "(that may be incomplete), to make recommendations and to enable a business "
            "solution or range of solutions to be achieved."
        ),
    },
    {
        "code": "AS4",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Communication to diverse audiences",
        "description": (
            "Communicate concepts and present in a manner appropriate to diverse "
            "audiences, adapting communication techniques accordingly."
        ),
    },
    {
        "code": "AS5",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Stakeholder expectation management",
        "description": (
            "Manage expectations and present user research insight, proposed solutions "
            "and/or test findings to clients and stakeholders."
        ),
    },
    {
        "code": "AS6",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "AI and data science direction",
        "description": (
            "Provide direction and technical guidance for the business with regard to "
            "AI and data science opportunities."
        ),
    },
    {
        "code": "AS7",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Autonomous and collaborative working",
        "description": (
            "Work autonomously and interact effectively within wide, multidisciplinary "
            "teams."
        ),
    },
    {
        "code": "AS8",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Stakeholder coordination",
        "description": (
            "Coordinate, negotiate with and manage expectations of diverse stakeholders "
            "and suppliers with conflicting priorities, interests and timescales."
        ),
    },
    {
        "code": "AS9",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Complex data manipulation",
        "description": (
            "Manipulate, analyse and visualise complex datasets."
        ),
    },
    {
        "code": "AS10",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Dataset and methodology selection",
        "description": (
            "Select datasets and methodologies most appropriate to the business problem."
        ),
    },
    {
        "code": "AS11",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Advanced maths and statistics",
        "description": (
            "Apply aspects of advanced maths and statistics relevant to AI and data "
            "science that deliver business outcomes."
        ),
    },
    {
        "code": "AS12",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Regulatory and ethical considerations",
        "description": (
            "Consider the associated regulatory, legal, ethical and governance issues "
            "when evaluating choices at each stage of the data process."
        ),
    },
    {
        "code": "AS13",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Resource and architecture identification",
        "description": (
            "Identify appropriate resources and architectures for solving a computational "
            "problem within the workplace."
        ),
    },
    {
        "code": "AS14",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Software engineering collaboration",
        "description": (
            "Work collaboratively with software engineers to ensure suitable testing "
            "and documentation processes are implemented."
        ),
    },
    {
        "code": "AS15",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "AI services and platforms",
        "description": (
            "Develop, build and maintain the services and platforms that deliver AI "
            "and data science."
        ),
    },
    {
        "code": "AS16",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Data management infrastructure",
        "description": (
            "Define requirements for, and supervise implementation of, and use data "
            "management infrastructure, including enterprise, private and public cloud "
            "resources and services."
        ),
    },
    {
        "code": "AS17",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Data curation and quality",
        "description": (
            "Consistently implement data curation and data quality controls."
        ),
    },
    {
        "code": "AS18",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Data system visualisation tools",
        "description": (
            "Develop tools that visualise data systems and structures for monitoring "
            "and performance."
        ),
    },
    {
        "code": "AS19",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Scalable infrastructure use",
        "description": (
            "Use scalable infrastructures, high performance networks, infrastructure "
            "and services management and operation to generate effective business "
            "solutions."
        ),
    },
    {
        "code": "AS20",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Efficient algorithm design",
        "description": (
            "Design efficient algorithms for accessing and analysing large amounts of "
            "data, including Application Programming Interfaces (API) to different "
            "databases and data sets."
        ),
    },
    {
        "code": "AS21",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Uncertainty quantification",
        "description": (
            "Identify and quantify different kinds of uncertainty in the outputs of "
            "data collection, experiments and analyses."
        ),
    },
    {
        "code": "AS22",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Scientific methods in data science",
        "description": (
            "Apply scientific methods in a systematic process through experimental "
            "design, exploratory data analysis and hypothesis testing to facilitate "
            "business decision making."
        ),
    },
    {
        "code": "AS23",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Dissemination of AI best practice",
        "description": (
            "Disseminate AI and data science practices across departments and in "
            "industry, promoting professional development and use of best practice."
        ),
    },
    {
        "code": "AS24",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Research and project management",
        "description": (
            "Apply research methodology and project management techniques appropriate "
            "to the organisation and products."
        ),
    },
    {
        "code": "AS25",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Programming and software practices",
        "description": (
            "Select and use programming languages and tools, and follow appropriate "
            "software development practices."
        ),
    },
    {
        "code": "AS26",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "AI technique selection",
        "description": (
            "Select and apply the most effective and appropriate AI and data science "
            "techniques to solve complex business problems."
        ),
    },
    {
        "code": "AS27",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Scoping AI requirements",
        "description": (
            "Analyse information, frame questions and conduct discussions with subject "
            "matter experts and assess existing data to scope new AI and data science "
            "requirements."
        ),
    },
    {
        "code": "AS28",
        "spec_code": "ST0763",
        "category": "skill",
        "title": "Independent decision-making",
        "description": (
            "Undertake independent, impartial decision-making respecting the opinions "
            "and views of others in complex, unpredictable and changing circumstances."
        ),
    },
    # Behaviours
    {
        "code": "AB1",
        "spec_code": "ST0763",
        "category": "behaviour",
        "title": "Work ethic and commitment",
        "description": (
            "A strong work ethic and commitment in order to meet the standards required."
        ),
    },
    {
        "code": "AB2",
        "spec_code": "ST0763",
        "category": "behaviour",
        "title": "Reliability and objectivity",
        "description": (
            "Reliable, objective and capable of independent and team working."
        ),
    },
    {
        "code": "AB3",
        "spec_code": "ST0763",
        "category": "behaviour",
        "title": "Integrity",
        "description": (
            "Acts with integrity with respect to ethical, legal and regulatory "
            "requirements, ensuring the protection of personal data, safety and security."
        ),
    },
    {
        "code": "AB4",
        "spec_code": "ST0763",
        "category": "behaviour",
        "title": "Initiative and ownership",
        "description": (
            "Initiative and personal responsibility to overcome challenges and take "
            "ownership for business solutions."
        ),
    },
    {
        "code": "AB5",
        "spec_code": "ST0763",
        "category": "behaviour",
        "title": "Continuous professional development",
        "description": (
            "Commitment to continuous professional development; maintaining their "
            "knowledge and skills in relation to AI developments that influence their "
            "work."
        ),
    },
    {
        "code": "AB6",
        "spec_code": "ST0763",
        "category": "behaviour",
        "title": "Confident communication",
        "description": (
            "Is comfortable and confident interacting with people from technical and "
            "non-technical backgrounds."
        ),
    },
]
