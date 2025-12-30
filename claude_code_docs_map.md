# RMCitecraft Documentation Map

> **For LLMs**: This compact index contains essential docs only.
> For complete documentation, see `docs/FULL_INDEX.md`.
> Last generated: 2025-12-30 18:27:31 UTC

**Essential docs**: 21 | 
**Total docs**: 87 (use Glob/Grep for full search)

## Getting Started

### [RMCitecraft](https://github.com/mikeiacovacci/RMCitecraft/blob/main/README.md)
*Topics: database, census, citation, batch, findagrave*

- Value Proposition
- Key Features
- How It Works
- Use Cases
- Requirements
- Technology Stack
- Installation
- Quick Start
- Documentation
- Caveats and Known Issues

## Project Overview

### [AGENTS.md](https://github.com/mikeiacovacci/RMCitecraft/blob/main/AGENTS.md)
*Topics: database, census, citation, batch, findagrave*

- Project Overview
- Communication Style
- Do's and Don'ts
- Setup & Build Steps
- Test Commands & CI
- Code Style & Formatting Rules
- Commit & PR Guidelines
- Security & Dependency Policies
- Project-Specific Context
- Common Tasks

### [CLAUDE.md](https://github.com/mikeiacovacci/RMCitecraft/blob/main/CLAUDE.md)
*Topics: database, census, citation, batch, findagrave*

- Quick Reference
- Project Overview
- Before Modifying Code
- Project Structure
- Database Safety (Critical)
- Citation Formatting
- Testing
- Configuration
- Playwright Browser Automation
- Key Files

## Reference

### [Batch State Database Schema Reference](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/BATCH_STATE_DATABASE_SCHEMA.md)
*Topics: database, census, citation, batch, findagrave*

- Overview
- Database Location
- Schema Version
- Tables
- Extracted Data JSON Formats
- Indexes
- Status State Machine
- Relationship to RootsMagic Database
- Maintenance
- Related Documentation

### [Census Extraction Database Schema Reference](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/CENSUS_EXTRACTION_DATABASE_SCHEMA.md)
*Topics: database, census, citation, batch, testing*

- Overview
- Database Location
- Schema Version
- Architecture
- Tables
- Features and Capabilities
- Sample Queries
- Cross-Database Queries with RootsMagic
- Recommended Use Cases
- Maintenance

### [Census Form Rendering Architecture](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/CENSUS_FORM_RENDERING.md)
*Topics: database, census, batch, automation*

- Overview
- Architecture Diagram
- Data Models
- Usage Examples
- Template Structure
- Quality Indicators
- CSS Classes
- Adding New Census Years
- File Locations
- Related Documentation

### [RMCitecraft Citation Style Guide](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/CITATION-STYLE-GUIDE.md)
*Topics: citation, evidence-explained, formatting, reference*

- Overview
- The Three Citation Forms
- Citation Format by Census Era
- Special Schedule Types
- Abbreviations Used
- Bibliography Format
- Source Name Format
- Design Decisions
- Validation Rules
- Compatibility Notes

### [RootsMagic Database Patterns](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/DATABASE_PATTERNS.md)
*Topics: database, census, citation, batch, testing*

- Database Connection
- Free-Form Citation Architecture
- Census Events: Shared Facts
- Key Database Conventions
- OwnerType Values
- MediaType Values

### [Database Integrity Testing Guide](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/DATABASE_TESTING.md)
*Topics: database, citation, batch, testing, ui*

- Why Comparison-Based Testing is Essential
- Critical Bugs Caught by Comparison Testing
- Methodology: Field-by-Field Comparison
- Required Tests for Each New Record Type
- Test Organization Pattern
- When to Run These Tests
- Reference Implementation
- Testing Philosophy

### [RootsMagic Database Reference Documentation](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/README.md)
*Topics: database, census, citation, batch, findagrave*

- Quick Navigation
- Documentation Purpose
- Critical Learnings from Database Analysis
- Testing Philosophy
- Document Organization
- How to Use This Documentation
- Key Reference Patterns
- Contribution Guidelines
- Related Documentation

### [RootsMagic 11 Schema Reference](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/reference/schema-reference.md)
*Topics: database, census, citation, ui, automation*

- Overview
- Database Characteristics
- Key Concepts
- Tables by Category
- Core Entities
- Events and Facts
- Sources and Citations
- Places
- Multimedia
- Research Management

## Architecture

### [Find a Grave Batch Processing Architecture](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/architecture/BATCH_PROCESSING_ARCHITECTURE.md)
*Topics: database, census, citation, batch, findagrave*

- Overview
- Architecture Components
- Batch Processing Workflow
- Configuration
- Using Resume Functionality
- Performance Metrics
- Error Handling
- Troubleshooting
- Architecture Decisions
- Testing

### [Census Batch Processing Architecture](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/architecture/CENSUS_BATCH_PROCESSING_ARCHITECTURE.md)
*Topics: database, census, citation, batch, findagrave*

- Overview
- Key Differences from Find a Grave Processing
- Architecture Components
- Batch Processing Workflow
- Configuration
- Validation Rules
- Resume Functionality
- Export to RootsMagic
- Error Handling
- Performance Metrics

## Database

### [RMCitecraft Documentation](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/README.md)
*Topics: database, census, citation, batch, findagrave*

- 📚 Documentation Categories
- 🚀 Quick Start Guides
- 🎯 Key Learnings from Database Analysis
- 📊 Documentation Map by Feature
- 🔍 Finding Documentation
- 📝 Documentation Standards
- 🔗 Related Documentation
- 📞 Getting Help

## Testing

### [E2E Testing Quick Start Guide](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/E2E-TESTING-QUICKSTART.md)
*Topics: census, citation, batch, testing, ui*

- What We Built
- Quick Start (3 Steps)
- Test Suites
- Before First Run
- What Tests Do
- Test Output Example
- Troubleshooting
- Advanced Usage
- Files Created
- Performance

### [End-to-End (E2E) Tests for FamilySearch Automation](https://github.com/mikeiacovacci/RMCitecraft/blob/main/tests/e2e/README.md)
*Topics: census, citation, batch, testing, ui*

- Overview
- Test Coverage
- Prerequisites
- Running Tests
- Test Output
- Troubleshooting
- Test Data
- CI/CD Integration
- Test Development
- Performance Benchmarks

## Archive

### [Census Batch Workflow Guide](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/misc/CENSUS-BATCH-WORKFLOW.md)
*Topics: user-guide, census, batch-processing*

- Overview
- Before You Begin
- Step 1: Select Census Year
- Step 2: Filter Citations
- Step 3: Start Batch Processing
- Step 4: Review Each Citation
- Step 5: Save or Skip
- Citation Format Output
- Year-Specific Notes
- Handling Special Cases

## User Guides

### [Frequently Asked Questions](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/user-guides/FAQ.md)
*Topics: faq, questions, help*

- General Questions
- Setup Questions
- Database Questions
- Citation Questions
- Processing Questions
- Image Questions
- Technical Questions
- Error Questions
- Support

### [Getting Started with RMCitecraft](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/user-guides/GETTING-STARTED.md)
*Topics: user-guide, installation, setup*

- What is RMCitecraft?
- Step 1: Install RMCitecraft
- Step 2: Configure Your Environment
- Step 3: Set Up Chrome for FamilySearch
- Step 4: Prepare Your Database
- Step 5: Start RMCitecraft
- Step 6: Process Your First Citation
- Understanding RMCitecraft's Assumptions
- Next Steps
- Getting Help

### [Prerequisites for RMCitecraft](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/user-guides/PREREQUISITES.md)
*Topics: setup, installation, requirements*

- Overview
- System Requirements
- Required Software
- Required Accounts
- Optional Components
- RootsMagic Database Preparation
- Chrome Configuration for FamilySearch
- Directory Structure
- Verification Checklist
- Common Issues

### [Troubleshooting Guide](https://github.com/mikeiacovacci/RMCitecraft/blob/main/docs/user-guides/TROUBLESHOOTING.md)
*Topics: troubleshooting, errors, support*

- Quick Diagnostics
- Installation Issues
- Database Connection Issues
- Chrome/FamilySearch Issues
- Citation Processing Issues
- Image Issues
- Performance Issues
- Recovery
- Getting More Help
- Common Error Messages Reference
