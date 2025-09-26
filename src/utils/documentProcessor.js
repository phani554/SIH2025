import axios from 'axios';
import Tesseract from 'tesseract.js';

const GEMINI_API_KEY = 'AIzaSyAllDbwaC_grxAroMNnicJTnXyONnwSFNE';
const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent';

// Convert file to base64 for image processing
const convertToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

// Extract text from different file types
export const extractTextFromFile = async (file) => {
  const fileType = file.type;
  const fileName = file.name.toLowerCase();

  try {
    if (fileType.includes('image') || fileName.includes('.jpg') || fileName.includes('.png') || fileName.includes('.jpeg')) {
      // OCR for images with better language support
      const result = await Tesseract.recognize(file, 'eng+hin+mal', {
        logger: m => console.log(m)
      });
      return result.data.text;
    }
    else if (fileType.includes('pdf') || fileName.includes('.pdf')) {
      // For PDF files, we'll use a simple text extraction
      return await extractTextFromPDF(file);
    }
    else if (fileType.includes('text') || fileName.includes('.txt')) {
      // Plain text files
      return await file.text();
    }
    else {
      // For other document types, try to read as text
      return await file.text();
    }
  } catch (error) {
    console.error('Error extracting text:', error);
    throw new Error('Failed to extract text from document');
  }
};

// Simple PDF text extraction (for demo purposes)
const extractTextFromPDF = async (file) => {
  // This is a simplified version. In production, use pdf-parse or similar
  const arrayBuffer = await file.arrayBuffer();
  const text = new TextDecoder().decode(arrayBuffer);

  // Extract readable text (this is very basic)
  const textMatch = text.match(/BT\s*(.*?)\s*ET/g);
  if (textMatch) {
    return textMatch.map(match => match.replace(/BT\s*|\s*ET/g, '')).join(' ');
  }

  return "PDF content detected - please use OCR for scanned PDFs";
};

// Step 1: Get Department Classification
export const getDepartmentClassification = async (documentText, fileName, fileType) => {
  const prompt = `You are an expert document classifier for KMRL (Kochi Metro Rail Limited), India's premier metro rail system in Kochi, Kerala.

🚇 **KMRL CONTEXT:**
KMRL operates the Kochi Metro, serving passengers across Kochi with modern metro rail services. The organization has multiple departments handling different aspects of metro operations, maintenance, administration, and passenger services.

📄 **DOCUMENT TO ANALYZE:**
File Name: ${fileName}
File Type: ${fileType}
Content: ${documentText}

🎯 **CLASSIFICATION TASK:**
Analyze this document and determine which KMRL department it belongs to. Consider the content, context, and purpose.

**KMRL DEPARTMENTS:**
- **Engineering**: Technical drawings, infrastructure plans, track maintenance, electrical systems, signaling, construction projects
- **Operations**: Train schedules, passenger services, station operations, service disruptions, operational procedures
- **Maintenance**: Rolling stock maintenance, infrastructure upkeep, preventive maintenance, repair schedules, equipment servicing
- **Safety**: Safety protocols, incident reports, emergency procedures, safety training, compliance with metro safety standards
- **Finance**: Invoices, payments, budgets, financial reports, procurement costs, revenue analysis
- **HR**: Employee policies, recruitment, training programs, staff schedules, personnel matters
- **Legal**: Contracts, legal opinions, regulatory compliance, legal notices, policy documents
- **Procurement**: Vendor management, purchase orders, supplier contracts, equipment procurement

🔍 **ANALYSIS REQUIREMENTS:**
1. Read the document content carefully
2. Identify key terms, context, and subject matter
3. Match content to appropriate KMRL department
4. Provide reasoning for the classification

**RESPONSE FORMAT (JSON):**
{
  "department": "Exact department name from the list above",
  "confidence": "High/Medium/Low - your confidence in this classification",
  "reasoning": "Detailed explanation of why this document belongs to this department, citing specific content from the document",
  "keywords": ["List of key terms that led to this classification"],
  "alternativeDepartment": "If uncertain, mention the second most likely department or 'None'"
}

**IMPORTANT:** 
- If the document content is unclear or insufficient, set confidence to "Low"
- If document is in Malayalam/Hindi, translate key terms to English in your reasoning
- Focus on KMRL-specific context and metro rail operations
- Be precise and specific in your reasoning`;

  return await makeGeminiRequest(prompt);
};

// Step 2: Generate Detailed Summary
export const generateDetailedSummary = async (documentText, fileName, department) => {
  const prompt = `You are a senior analyst at KMRL (Kochi Metro Rail Limited) specializing in the ${department} department.

🚇 **KMRL CONTEXT:**
You have extensive knowledge of KMRL operations, policies, and procedures. You understand the specific needs and challenges of the ${department} department in the context of metro rail operations in Kochi.

📄 **DOCUMENT TO SUMMARIZE:**
File Name: ${fileName}
Department: ${department}
Content: ${documentText}

📝 **SUMMARY REQUIREMENTS:**
Create a comprehensive, detailed summary that captures all important information relevant to KMRL operations.

**SUMMARY STRUCTURE:**
1. **Document Overview**: What type of document this is and its primary purpose
2. **Key Information**: All important details, facts, figures, dates, and specifications
3. **KMRL Relevance**: How this relates to metro operations, specific stations, routes, or services
4. **Technical Details**: Any technical specifications, procedures, or requirements mentioned
5. **Financial Implications**: Any costs, budgets, or financial impacts (if applicable)
6. **Timeline**: Important dates, deadlines, or schedules mentioned
7. **Stakeholders**: People, departments, or external parties involved

**RESPONSE FORMAT (JSON):**
{
  "documentType": "Specific type of document (e.g., Maintenance Report, Safety Circular, Invoice, etc.)",
  "overview": "2-3 sentence overview of what this document is about",
  "detailedSummary": "Comprehensive 4-6 paragraph summary covering all important aspects",
  "keyPoints": ["List of 5-8 most important points from the document"],
  "technicalDetails": "Any technical specifications, procedures, or requirements (or 'None mentioned' if not applicable)",
  "financialInfo": "Cost details, budget information, or financial implications (or 'None mentioned' if not applicable)",
  "locations": ["Specific metro stations, depots, or areas mentioned (or empty array if none)"],
  "timeline": "Important dates, deadlines, or schedules mentioned (or 'No specific timeline mentioned')",
  "stakeholders": ["People, roles, departments, or organizations mentioned"]
}

**IMPORTANT:**
- Be thorough and detailed in your analysis
- Include specific numbers, dates, and technical terms from the document
- If document is in Malayalam/Hindi, translate important information to English
- Focus on information relevant to KMRL metro operations
- If certain information is not present in the document, clearly state "Not mentioned" or "Not applicable"`;

  return await makeGeminiRequest(prompt);
};

// Step 3: Extract Purpose and Actions
export const extractPurposeAndActions = async (documentText, fileName, department, summary) => {
  const prompt = `You are a KMRL ${department} department manager with deep understanding of metro rail operations and organizational procedures.

🚇 **CONTEXT:**
Document: ${fileName}
Department: ${department}
Summary: ${summary}

📋 **DOCUMENT CONTENT:**
${documentText}

🎯 **PURPOSE & ACTION ANALYSIS:**
Analyze this document to understand its specific purpose and identify all required actions.

**ANALYSIS REQUIREMENTS:**
1. **Primary Purpose**: What is the main objective or reason for this document?
2. **Secondary Purposes**: Any additional objectives or goals
3. **Action Items**: Specific tasks that need to be completed
4. **Responsible Parties**: Who needs to take action
5. **Urgency Assessment**: How urgent are these actions based on content
6. **Dependencies**: What needs to happen before actions can be taken

**RESPONSE FORMAT (JSON):**
{
  "primaryPurpose": "Main objective or reason for this document",
  "secondaryPurposes": ["Additional objectives if any, or empty array"],
  "actionItems": [
    {
      "action": "Specific action required",
      "responsible": "Who should do this (role/department)",
      "priority": "High/Medium/Low",
      "timeframe": "When this should be done (if mentioned)"
    }
  ],
  "urgencyLevel": "Critical/High/Medium/Low",
  "urgencyReason": "Detailed explanation of why this urgency level was assigned based on document content",
  "dependencies": ["What needs to happen first, or empty array if none"],
  "expectedOutcome": "What should result from completing these actions",
  "riskIfNotActioned": "Potential consequences if actions are not taken"
}

**URGENCY CRITERIA:**
- **Critical**: Safety issues, emergency situations, system failures, regulatory deadlines
- **High**: Operational disruptions, important deadlines within 48 hours, significant financial impact
- **Medium**: Regular operations, deadlines within a week, moderate impact
- **Low**: Routine matters, long-term planning, informational documents

**IMPORTANT:**
- Base urgency assessment on actual document content, not assumptions
- If no specific deadline is mentioned, state "No deadline specified"
- Consider KMRL operational context when assessing urgency
- Be specific about actions and responsibilities`;

  return await makeGeminiRequest(prompt);
};

// Step 4: Extract Additional Details
export const extractAdditionalDetails = async (documentText, fileName, department) => {
  const prompt = `You are a KMRL compliance and documentation specialist with expertise in metro rail regulations and organizational procedures.

🚇 **DOCUMENT ANALYSIS:**
File: ${fileName}
Department: ${department}
Content: ${documentText}

🔍 **DETAILED EXTRACTION:**
Extract all additional important details that would be relevant for KMRL operations and compliance.

**RESPONSE FORMAT (JSON):**
{
  "keyPersons": ["Specific names, roles, or positions mentioned (or empty array if none)"],
  "deadline": "Specific deadline mentioned in the document (or 'No deadline mentioned')",
  "complianceRequired": "Yes/No - whether this involves regulatory compliance",
  "complianceDetails": "Details about compliance requirements (or 'Not applicable')",
  "riskLevel": "High/Medium/Low",
  "riskAssessment": "Detailed explanation of risk level based on document content",
  "estimatedCost": "Any cost figures mentioned (or 'No cost mentioned')",
  "costBreakdown": "Breakdown of costs if provided (or 'Not provided')",
  "vendors": ["External companies or suppliers mentioned (or empty array)"],
  "equipmentMentioned": ["Specific equipment, systems, or infrastructure mentioned"],
  "regulatoryBodies": ["Government agencies, regulatory bodies mentioned (e.g., CMRS, MoHUA)"],
  "tags": ["Relevant categorization tags based on content"],
  "documentSource": "Where this document likely originated (internal/external/vendor/regulatory)",
  "followUpRequired": "Yes/No - whether this document requires follow-up actions",
  "archivalImportance": "High/Medium/Low - importance for record keeping"
}

**RISK ASSESSMENT CRITERIA:**
- **High**: Safety hazards, regulatory non-compliance, significant financial loss, operational shutdown
- **Medium**: Service disruptions, moderate financial impact, compliance concerns
- **Low**: Routine operations, minor issues, informational content

**COMPLIANCE CONSIDERATIONS:**
- Commissioner of Metro Rail Safety (CMRS) requirements
- Ministry of Housing & Urban Affairs (MoHUA) guidelines
- Local government regulations
- Environmental compliance
- Safety standards and protocols

**IMPORTANT:**
- Only include information that is explicitly mentioned in the document
- If information is not available, clearly state "Not mentioned" or "Not applicable"
- Be accurate with financial figures and dates
- Consider KMRL-specific operational context`;

  return await makeGeminiRequest(prompt);
};

// Helper function to make Gemini API requests with error handling
const makeGeminiRequest = async (prompt) => {
  try {
    const response = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [{
          parts: [{
            text: prompt
          }]
        }]
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    const aiResponse = response.data.candidates[0].content.parts[0].text;

    // Extract JSON from the response
    const jsonMatch = aiResponse.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    } else {
      throw new Error('Could not parse AI response as JSON');
    }
  } catch (error) {
    console.error('Gemini API Error:', error);
    throw new Error(`Failed to process with AI: ${error.message}`);
  }
};

// Main processing function that combines all steps
export const processWithGemini = async (documentText, fileName, fileType, onProgress) => {
  try {
    // Step 1: Department Classification
    onProgress('classifying', 25);
    const departmentResult = await getDepartmentClassification(documentText, fileName, fileType);

    // Step 2: Detailed Summary
    onProgress('summarizing', 50);
    const summaryResult = await generateDetailedSummary(documentText, fileName, departmentResult.department);

    // Step 3: Purpose and Actions
    onProgress('extracting-purpose', 75);
    const purposeResult = await extractPurposeAndActions(documentText, fileName, departmentResult.department, summaryResult.detailedSummary);

    // Step 4: Additional Details
    onProgress('extracting-details', 90);
    const detailsResult = await extractAdditionalDetails(documentText, fileName, departmentResult.department);

    // Combine all results
    return {
      ...departmentResult,
      ...summaryResult,
      ...purposeResult,
      ...detailsResult,
      processedAt: new Date().toISOString(),
      fileName: fileName,
      fileType: fileType
    };

  } catch (error) {
    console.error('Processing error:', error);
    throw error;
  }
};

// Fallback parser for AI response
const parseAIResponse = (response) => {
  return {
    department: extractField(response, 'department') || 'General',
    summary: extractField(response, 'summary') || 'Document analysis completed',
    purpose: extractField(response, 'purpose') || 'General document processing',
    urgency: extractField(response, 'urgency') || 'Medium',
    actionItems: ['Review document', 'Take appropriate action'],
    keyPersons: ['Department Head', 'Relevant Staff'],
    deadline: extractField(response, 'deadline') || 'Not specified',
    documentType: extractField(response, 'documentType') || 'General Document',
    tags: ['KMRL', 'Document'],
    riskLevel: extractField(response, 'riskLevel') || 'Medium',
    complianceRequired: extractField(response, 'complianceRequired') || 'No',
    estimatedCost: extractField(response, 'estimatedCost') || 'Not specified',
    location: extractField(response, 'location') || 'General'
  };
};

const extractField = (text, field) => {
  const regex = new RegExp(`${field}[:\s]*([^\n]+)`, 'i');
  const match = text.match(regex);
  return match ? match[1].trim() : null;
};

// Get department color coding
export const getDepartmentColor = (department) => {
  const colors = {
    'Engineering': '#FF6B6B',
    'HR': '#4ECDC4',
    'Finance': '#45B7D1',
    'Safety': '#FFA07A',
    'Legal': '#98D8C8',
    'Procurement': '#F7DC6F',
    'Operations': '#BB8FCE',
    'Maintenance': '#85C1E9'
  };
  return colors[department] || '#95A5A6';
};

// Get urgency color
export const getUrgencyColor = (urgency) => {
  const colors = {
    'Critical': '#E74C3C',
    'High': '#E67E22',
    'Medium': '#F39C12',
    'Low': '#27AE60'
  };
  return colors[urgency] || '#95A5A6';
};