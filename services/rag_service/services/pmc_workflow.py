#!/usr/bin/env python3
"""
PMC Workflow System
Redemption, Deemed Conveyance, Feasibility Reports, Project Tracking
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
WORKFLOWS_DIR = DATA_DIR / "workflows"
PROJECTS_DIR = DATA_DIR / "projects"
TEMPLATES_DIR = DATA_DIR / "templates"

WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


class ProjectStatus(Enum):
    DRAFT = "draft"
    FEASIBILITY = "feasibility"
    TENDER = "tender"
    AGREEMENT = "agreement"
    DDR_REPORT = "ddr_report"
    DEEMED_CONVEYANCE = "deemed_conveyance"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class WorkflowStage(Enum):
    INITIATION = "initiation"
    DOCUMENTATION = "documentation"
    COMPLIANCE_CHECK = "compliance_check"
    TENDER_PUBLICATION = "tender_publication"
    TENDER_EVALUATION = "tender_evaluation"
    AGREEMENT_SIGNING = "agreement_signing"
    DDR_SUBMISSION = "ddr_submission"
    DEEMED_CONVEYANCE = "deemed_conveyance"
    COMPLETED = "completed"


@dataclass
class PlotDetails:
    survey_no: str = ""
    area_sq_m: float = 0.0
    area_sq_ft: float = 0.0
    road_width_m: float = 0.0
    zone_type: str = ""
    dp_remarks: str = ""
    pr_card_data: dict = field(default_factory=dict)
    zone_regulations: dict = field(default_factory=dict)


@dataclass
class Society:
    name: str = ""
    registration_no: str = ""
    address: str = ""
    total_members: int = 0
    voting_quorum: int = 0
    contact_person: str = ""
    contact_email: str = ""
    contact_phone: str = ""


@dataclass
class Builder:
    name: str = ""
    registration_no: str = ""
    address: str = ""
    contact_person: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    experience_years: int = 0
    past_projects: int = 0


@dataclass
class Tender:
    tender_id: str = ""
    type: str = "e_tender"  # e_tender or traditional
    publication_date: datetime = None
    submission_deadline: datetime = None
    technical_bid_opening: datetime = None
    financial_bid_opening: datetime = None
    reserved_quotas: dict = field(default_factory=dict)
    eligibility_criteria: dict = field(default_factory=dict)
    status: str = "draft"


@dataclass
class Document:
    doc_id: str = ""
    doc_type: str = ""  # provisional_agreement, da, poa, ddr_report, feasibility
    title: str = ""
    file_path: str = ""
    created_at: datetime = None
    status: str = "draft"
    content: str = ""


@dataclass
class WorkflowStep:
    step_id: str = ""
    stage: str = ""
    name: str = ""
    description: str = ""
    responsible_party: str = ""  # pmc, builder, society, ddr, lawyer
    status: str = "pending"
    completed_at: datetime = None
    notes: str = ""
    dependencies: List[str] = field(default_factory=list)
    documents_required: List[str] = field(default_factory=list)
    documents_generated: List[str] = field(default_factory=list)


@dataclass
class Project:
    project_id: str = ""
    name: str = ""
    society: Society = None
    plot: PlotDetails = None
    status: ProjectStatus = ProjectStatus.DRAFT
    current_stage: WorkflowStage = WorkflowStage.INITIATION
    created_at: datetime = None
    updated_at: datetime = None
    estimated_completion: datetime = None

    # Tenders
    tenders: List[Tender] = field(default_factory=list)

    # Documents
    documents: List[Document] = field(default_factory=list)

    # Workflow
    workflow_steps: List[WorkflowStep] = field(default_factory=list)

    # Compliance
    compliance_checked: bool = False
    compliance_notes: str = ""

    # Deemed Conveyance
    deemed_conveyance_initiated: bool = False
    deemed_conveyance_date: datetime = None
    lawyer_engaged: bool = False
    lawyer_name: str = ""

    # Meta
    pmc_name: str = ""
    notes: str = ""


class PMCWorkflowEngine:
    """Workflow engine for PMC operations"""

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict:
        """Load document templates"""
        templates = {
            "provisional_agreement": TEMPLATES_DIR / "provisional_agreement.txt",
            "da": TEMPLATES_DIR / "development_agreement.txt",
            "poa": TEMPLATES_DIR / "poa.txt",
            "ddr_report": TEMPLATES_DIR / "ddr_report.txt",
            "feasibility": TEMPLATES_DIR / "feasibility_report.txt",
            "deemed_conveyance_notice": TEMPLATES_DIR / "deemed_conveyance_notice.txt",
        }

        # Create default templates if not exist
        for name, path in templates.items():
            if not path.exists():
                self._create_default_template(name, path)

        return templates

    def _create_default_template(self, name: str, path: Path):
        """Create default template"""
        templates_content = {
            "provisional_agreement": """PROVISIONAL AGREEMENT FOR REDEVELOPMENT

This Agreement is entered on {date} between:
Society: {society_name} (hereinafter called "Society")
And
Developer: {builder_name} (hereinafter called "Developer")

1. PROJECT DETAILS
   Project Name: {project_name}
   Plot Address: {plot_address}
   Survey No: {survey_no}
   Plot Area: {area_sq_m} sq.mtrs

2. TERMS AND CONDITIONS
   a) The Developer agrees to redevelop the property as per DCPR regulations.
   b) The Society agrees to handover possession of the premises.
   c) FSI applicable: {fsi}
   d) Timeline: {timeline} months from date of commencement.

3. OBLIGATIONS
   Society Obligations:
   - Handover possession within 60 days
   - Provide all original documents
   - Obtain 70% member consent

   Developer Obligations:
   - Complete construction within agreed timeline
   - Provide RERA carpet area as committed
   - Pay agreed rent during construction

4. DISPUTE RESOLUTION
   Any dispute shall be referred to arbitration.

Signed on {date}

For Society:                     For Developer:
_________________                 _________________
President                         Authorized Signatory
{society_name}                   {builder_name}
""",
            "development_agreement": """DEVELOPMENT AGREEMENT

Date: {date}

This Development Agreement ("Agreement") is made between:
{society_name} (Society) having Registration No: {society_reg_no}
AND
{builder_name} (Developer) having Registration No: {builder_reg_no}

WHEREAS the Society is seized of the property bearing Survey No. {survey_no}
AND WHEREAS the Developer has agreed to undertake the redevelopment...

CLAUSE 1: DEFINITIONS
" FSI" means Floor Space Index as per DCPR 2034
" RERA Carpet Area" means the carpet area as defined under RERA

CLAUSE 2: SCOPE OF WORK
The Developer shall construct total {total_bua} sq.ft. comprising of:
- Rehabilitation area: {rehab_area} sq.ft.
- Saleable area: {saleable_area} sq.ft.

CLAUSE 3: CONSIDERATION
The Developer shall pay/ provide:
- Corpus Fund: Rs. {corpus_fund}
- Rent during construction: Rs. {rent_per_month}/month

CLAUSE 4: TIMELINES
Commencement Date: {commencement_date}
Completion Date: {completion_date}
Tolerable delay: 6 months

CLAUSE 5: DEEMED CONVEYANCE
The Society shall execute Deemed Conveyance deed within 60 days of 
completion certificate...

Signed this {date} day of {month} {year}

Witness 1:                    Witness 2:
_________________             _________________

For Society:                 For Developer:
{society_name}               {builder_name}
""",
            "poa": """POWER OF ATTORNEY

Date: {date}

Know all men by these presents, I/We {names} the owner(s) of flat no(s) {flat_nos} 
in {society_name} ("Society") do hereby irrevocably appoint and authorize 
{builder_name} ("Attorney") to act on my/our behalf for the following:

1. To sign all documents related to redevelopment of the Society property.
2. To appear before any government authority or court.
3. To submit applications, receive approvals.
4. To execute sale agreements, conveyance deeds.

This Power of Attorney is valid for a period of {validity} years from the date hereof.

Signed this {date}

Owner 1:                       Owner 2:
_________________              _________________
Flat No:                       Flat No:
""",
            "ddr_report": """DISTRICT DEPUTY REGISTRAR (DDR) REPORT
Project: {project_name}
Society: {society_name}
Date: {date}

1. PROJECT DETAILS
   Survey No: {survey_no}
   Plot Area: {area_sq_m} sq.mtrs
   Zone: {zone_type}
   DCPR Scheme: {scheme}

2. DOCUMENT CHECKLIST
   [ ] Society Resolution (70% consent)
   [ ] Original Share Certificates
   [ ] Property Card
   [ ] Development Agreement
   [ ] Plans approved by MCGM
   [ ] NOC from existing tenants
   [ ] Fire NOC
   [ ] Structural Stability Certificate
   [ ] Encumbrance Certificate
   [ ] Society Registration Certificate

3. COMPLIANCE STATUS
   DCPR 33(7B) / 33(20B): {dcpr_compliance}
   FSI Calculations: {fsi_details}
   Premium Paid: {premium_status}

4. FINANCIAL SUMMARY
   Total BUA: {total_bua} sq.ft.
   Rehab Area: {rehab_area} sq.ft.
   Saleable Area: {saleable_area} sq.ft.
   Estimated Revenue: Rs. {revenue} Cr
   Estimated Cost: Rs. {cost} Cr

5. RECOMMENDATION
   {recommendation}

Submitted by: {pmc_name}
Date: {date}
""",
            "feasibility": """FEASIBILITY REPORT
Project: {project_name}
Prepared by: {pmc_name}
Date: {date}

1. PROPERTY DETAILS
   Survey No: {survey_no}
   Address: {address}
   Plot Area: {area_sq_m} sq.m ({area_sq_ft} sq.ft.)
   Road Width: {road_width}m
   Zone: {zone_type}

2. ZONING ANALYSIS
   Permissible Use: {permissible_use}
   Prohibited Uses: {prohibited_uses}
   Setback Requirements: {setback_requirements}

3. FSI ANALYSIS
   Basic FSI: {basic_fsi}
   Incentive FSI: {incentive_fsi}
   Premium FSI Available: {premium_fsi}
   Maximum Permissible: {max_fsi}
   Total BUA: {total_bua} sq.ft.

4. REGULATORY COMPLIANCE
   DCPR 33(7B): {dcpr_7b}
   DCPR 33(20B): {dcpr_20b}
   DCPR 30(A): {dcpr_30a}
   Environment Clearances: {env_clearances}
   Fire NOC Required: {fire_noc}

5. FINANCIAL VIABILITY
   Estimated Construction Cost: Rs. {construction_cost} Cr
   Estimated Revenue: Rs. {revenue} Cr
   Profit Margin: {margin}%
   Payback Period: {payback} months

6. RECOMMENDATION
   {recommendation}

7. NEXT STEPS
   {next_steps}
""",
            "deemed_conveyance_notice": """NOTICE FOR INITIATION OF DEEMED CONVEYANCE

Date: {date}

To,
The Promoter/Developer: {developer_name}
Address: {developer_address}

Sub: Notice under Section 11(4) of RERA for Deemed Conveyance

Dear Sir/Madam,

We, the allottees/flat owners of {society_name} ("Society") hereby give you notice
of our intention to make deemed conveyance of the property bearing Survey No: {survey_no}

1. The Society was formed on {formation_date}
2. We have been in continuous possession since {possession_date}
3. You have failed to execute conveyance deed despite {years} years from completion

We call upon you to execute the Deed of Conveyance within 30 days of receipt of this notice,
failing which we will proceed with deemed conveyance under Section 11(4) of RERA.

Documents enclosed:
1. Society Registration Certificate
2. Share Certificates
3. Occupancy Certificates
4. Payment receipts

For {society_name},
_________________
President
Date: {date}
""",
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        if name in templates_content:
            path.write_text(templates_content[name])

    def create_project(
        self,
        name: str,
        society: Society,
        plot: PlotDetails,
        pmc_name: str = "Default PMC",
    ) -> Project:
        """Create a new project with workflow"""
        project = Project(
            project_id=str(uuid.uuid4())[:8].upper(),
            name=name,
            society=society,
            plot=plot,
            pmc_name=pmc_name,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status=ProjectStatus.DRAFT,
            current_stage=WorkflowStage.INITIATION,
        )

        # Initialize workflow steps
        project.workflow_steps = self._create_workflow_steps()

        # Estimate completion
        project.estimated_completion = datetime.now() + timedelta(days=730)  # 2 years

        self.save_project(project)
        return project

    def _create_workflow_steps(self) -> List[WorkflowStep]:
        """Create standard workflow steps for redevelopment"""
        return [
            WorkflowStep(
                step_id="step_1",
                stage="initiation",
                name="Project Initiation",
                description="Create project, collect society details, obtain mandate",
                responsible_party="pmc",
                dependencies=[],
                documents_required=["Society Resolution", "Member Consent Form"],
            ),
            WorkflowStep(
                step_id="step_2",
                stage="documentation",
                name="Documentation Collection",
                description="Collect PR Card, Property Card, Society Documents",
                responsible_party="pmc",
                dependencies=["step_1"],
                documents_required=["Property Card", "Share Certificates", "NOC"],
            ),
            WorkflowStep(
                step_id="step_3",
                stage="compliance_check",
                name="Feasibility & Compliance Check",
                description="Analyze zone regulations, FSI, generate feasibility report",
                responsible_party="pmc",
                dependencies=["step_2"],
                documents_required=["Feasibility Report"],
            ),
            WorkflowStep(
                step_id="step_4",
                stage="tender_publication",
                name="Tender Publication",
                description="Publish E-Tender or Traditional Tender",
                responsible_party="pmc",
                dependencies=["step_3"],
                documents_required=["Tender Document", "Eligibility Criteria"],
            ),
            WorkflowStep(
                step_id="step_5",
                stage="tender_evaluation",
                name="Tender Evaluation",
                description="Evaluate bids, compare offers, select builder",
                responsible_party="pmc",
                dependencies=["step_4"],
                documents_required=["Comparative Statement", "Evaluation Report"],
            ),
            WorkflowStep(
                step_id="step_6",
                stage="agreement_signing",
                name="Agreement Signing",
                description="Execute Development Agreement, POA",
                responsible_party="lawyer",
                dependencies=["step_5"],
                documents_required=[
                    "Development Agreement",
                    "POA",
                    "Provisional Agreement",
                ],
            ),
            WorkflowStep(
                step_id="step_7",
                stage="ddr_submission",
                name="DDR Report Submission",
                description="Prepare and submit DDR report to Registrar",
                responsible_party="pmc",
                dependencies=["step_6"],
                documents_required=["DDR Report", "Complete File"],
            ),
            WorkflowStep(
                step_id="step_8",
                stage="deemed_conveyance",
                name="Deemed Conveyance Initiation",
                description="Initiate deemed conveyance if required",
                responsible_party="lawyer",
                dependencies=["step_7"],
                documents_required=["Deemed Conveyance Notice", "Court Application"],
            ),
            WorkflowStep(
                step_id="step_9",
                stage="completed",
                name="Project Completion",
                description="Final handover, occupation certificate",
                responsible_party="pmc",
                dependencies=["step_8"],
                documents_required=["OC", "Final NOC"],
            ),
        ]

    def get_available_steps(self, project: Project) -> List[WorkflowStep]:
        """Get steps that can be started (dependencies met)"""
        completed_ids = {
            s.step_id for s in project.workflow_steps if s.status == "completed"
        }

        available = []
        for step in project.workflow_steps:
            if step.status == "pending":
                deps_met = all(dep in completed_ids for dep in step.dependencies)
                if deps_met:
                    available.append(step)

        return available

    def update_step_status(
        self, project: Project, step_id: str, status: str, notes: str = ""
    ) -> Project:
        """Update workflow step status"""
        for step in project.workflow_steps:
            if step.step_id == step_id:
                step.status = status
                if status == "completed":
                    step.completed_at = datetime.now()
                if notes:
                    step.notes = notes
                break

        # Update project status based on completed steps
        project.updated_at = datetime.now()
        completed_count = sum(
            1 for s in project.workflow_steps if s.status == "completed"
        )

        if completed_count >= 8:
            project.status = ProjectStatus.COMPLETED
            project.current_stage = WorkflowStage.COMPLETED
        elif completed_count >= 6:
            project.status = ProjectStatus.DEEMED_CONVEYANCE
            project.current_stage = WorkflowStage.DEEMED_CONVEYANCE
        elif completed_count >= 4:
            project.status = ProjectStatus.DDR_REPORT
            project.current_stage = WorkflowStage.DDR_SUBMISSION
        elif completed_count >= 2:
            project.status = ProjectStatus.TENDER
            project.current_stage = WorkflowStage.TENDER_EVALUATION
        elif completed_count >= 1:
            project.status = ProjectStatus.FEASIBILITY
            project.current_stage = WorkflowStage.COMPLIANCE_CHECK

        self.save_project(project)
        return project

    def generate_document(
        self, project: Project, doc_type: str, output_dir: Path = None
    ) -> Document:
        """Generate document from template"""
        if output_dir is None:
            output_dir = PROJECTS_DIR / project.project_id / "documents"
        output_dir.mkdir(parents=True, exist_ok=True)

        template_path = self.templates.get(doc_type)
        if not template_path or not template_path.exists():
            raise ValueError(f"Template not found: {doc_type}")

        template = template_path.read_text()

        # Prepare context
        context = self._prepare_doc_context(project, doc_type)

        # Replace placeholders
        content = template
        for key, value in context.items():
            content = content.replace(f"{{{key}}}", str(value))

        # Create document
        doc = Document(
            doc_id=str(uuid.uuid4())[:8].upper(),
            doc_type=doc_type,
            title=self._get_doc_title(doc_type),
            created_at=datetime.now(),
            status="generated",
            content=content,
        )

        # Save file
        filename = f"{doc_type}_{doc.doc_id}.txt"
        doc.file_path = str(output_dir / filename)
        Path(doc.file_path).write_text(content)

        # Add to project
        project.documents.append(doc)
        self.save_project(project)

        return doc

    def _prepare_doc_context(self, project: Project, doc_type: str) -> Dict:
        """Prepare context variables for document"""
        society = project.society
        plot = project.plot

        context = {
            "date": datetime.now().strftime("%d/%m/%Y"),
            "year": datetime.now().year,
            "month": datetime.now().strftime("%B"),
            "project_name": project.name,
            "society_name": society.name,
            "society_reg_no": society.registration_no,
            "survey_no": plot.survey_no,
            "area_sq_m": plot.area_sq_m,
            "area_sq_ft": plot.area_sq_ft,
            "road_width": plot.road_width_m,
            "zone_type": plot.zone_type,
            "pmc_name": project.pmc_name,
            "builder_name": "TBD",
            "builder_reg_no": "TBD",
        }

        if doc_type in ["feasibility", "ddr_report"]:
            # Add DCPR calculations
            from property_card_workflow import DCPRCalculator, PropertyCard

            card = PropertyCard(
                survey_no=plot.survey_no,
                plot_area_sq_m=plot.area_sq_m,
                road_width_m=plot.road_width_m,
                zone_type=plot.zone_type,
            )

            calc = DCPRCalculator()
            config = calc.calculate_scheme(
                "33(7B)",
                plot.area_sq_m,
                plot.road_width_m,
                plot.zone_type,
                affordable_housing_pct=70,
            )

            context.update(
                {
                    "address": society.address,
                    "basic_fsi": config.basic_fsi,
                    "incentive_fsi": config.incentive_fsi,
                    "premium_fsi": config.premium_fsi,
                    "max_fsi": config.max_permissible_fsi,
                    "total_bua": int(
                        plot.area_sq_ft * (config.basic_fsi + config.incentive_fsi)
                    ),
                    "scheme": "33(7B)",
                    "dcpr_7b": "Applicable"
                    if config.basic_fsi > 0
                    else "Not Applicable",
                    "dcpr_20b": "Check eligibility",
                    "dcpr_30a": "Check road frontage",
                    "dcpr_compliance": "Compliant",
                    "fsi_details": f"Basic: {config.basic_fsi}, Incentive: {config.incentive_fsi}",
                    "premium_status": "To be calculated",
                    "construction_cost": 0,
                    "revenue": 0,
                    "margin": 0,
                    "payback": 0,
                    "rehab_area": int(plot.area_sq_ft * config.basic_fsi * 0.7),
                    "saleable_area": int(plot.area_sq_ft * config.basic_fsi * 0.3),
                    "recommendation": "Proceed with redevelopment",
                    "next_steps": "1. Obtain society resolution\n2. Publish tender",
                    "permissible_use": "Residential",
                    "prohibited_uses": "Industrial, Hazardous",
                    "setback_requirements": "As per DCPR Table 1",
                    "env_clearances": "Required if area > 20,000 sq.m",
                    "fire_noc": "Yes, required",
                }
            )

        return context

    def _get_doc_title(self, doc_type: str) -> str:
        titles = {
            "provisional_agreement": "Provisional Agreement for Redevelopment",
            "da": "Development Agreement",
            "poa": "Power of Attorney",
            "ddr_report": "DDR Report for Registrar",
            "feasibility": "Feasibility Report",
            "deemed_conveyance_notice": "Deemed Conveyance Notice",
        }
        return titles.get(doc_type, doc_type.replace("_", " ").title())

    def initiate_deemed_conveyance(
        self,
        project: Project,
        developer_name: str,
        developer_address: str,
        lawyer_name: str,
    ) -> Project:
        """Initiate deemed conveyance process"""
        project.deemed_conveyance_initiated = True
        project.deemed_conveyance_date = datetime.now()
        project.lawyer_engaged = True
        project.lawyer_name = lawyer_name

        # Update workflow
        self.update_step_status(project, "step_7", "completed", "DDR Submitted")
        self.update_step_status(
            project,
            "step_8",
            "in_progress",
            f"Lawyer: {lawyer_name}, Developer: {developer_name}",
        )

        self.save_project(project)
        return project

    def save_project(self, project: Project):
        """Save project to disk"""
        path = PROJECTS_DIR / f"{project.project_id}.json"
        data = {
            "project_id": project.project_id,
            "name": project.name,
            "society": asdict(project.society) if project.society else None,
            "plot": asdict(project.plot) if project.plot else None,
            "status": project.status.value,
            "current_stage": project.current_stage.value,
            "created_at": project.created_at.isoformat()
            if project.created_at
            else None,
            "updated_at": project.updated_at.isoformat()
            if project.updated_at
            else None,
            "estimated_completion": project.estimated_completion.isoformat()
            if project.estimated_completion
            else None,
            "tenders": [asdict(t) for t in project.tenders],
            "documents": [asdict(d) for d in project.documents],
            "workflow_steps": [asdict(s) for s in project.workflow_steps],
            "compliance_checked": project.compliance_checked,
            "compliance_notes": project.compliance_notes,
            "deemed_conveyance_initiated": project.deemed_conveyance_initiated,
            "deemed_conveyance_date": project.deemed_conveyance_date.isoformat()
            if project.deemed_conveyance_date
            else None,
            "lawyer_engaged": project.lawyer_engaged,
            "lawyer_name": project.lawyer_name,
            "pmc_name": project.pmc_name,
            "notes": project.notes,
        }
        path.write_text(json.dumps(data, indent=2, default=str))

    def load_project(self, project_id: str) -> Project:
        """Load project from disk"""
        path = PROJECTS_DIR / f"{project_id}.json"
        if not path.exists():
            raise ValueError(f"Project not found: {project_id}")

        data = json.loads(path.read_text())

        project = Project()
        project.project_id = data["project_id"]
        project.name = data["name"]
        project.status = ProjectStatus(data["status"])
        project.current_stage = WorkflowStage(data["current_stage"])
        project.created_at = (
            datetime.fromisoformat(data["created_at"]) if data["created_at"] else None
        )
        project.updated_at = (
            datetime.fromisoformat(data["updated_at"]) if data["updated_at"] else None
        )
        project.estimated_completion = (
            datetime.fromisoformat(data["estimated_completion"])
            if data["estimated_completion"]
            else None
        )
        project.compliance_checked = data.get("compliance_checked", False)
        project.compliance_notes = data.get("compliance_notes", "")
        project.deemed_conveyance_initiated = data.get(
            "deemed_conveyance_initiated", False
        )
        project.deemed_conveyance_date = (
            datetime.fromisoformat(data["deemed_conveyance_date"])
            if data.get("deemed_conveyance_date")
            else None
        )
        project.lawyer_engaged = data.get("lawyer_engaged", False)
        project.lawyer_name = data.get("lawyer_name", "")
        project.pmc_name = data.get("pmc_name", "")
        project.notes = data.get("notes", "")

        if data.get("society"):
            project.society = Society(**data["society"])
        if data.get("plot"):
            project.plot = PlotDetails(**data["plot"])

        project.tenders = [Tender(**t) for t in data.get("tenders", [])]
        project.documents = [Document(**d) for d in data.get("documents", [])]
        project.workflow_steps = [
            WorkflowStep(**s) for s in data.get("workflow_steps", [])
        ]

        return project

    def list_projects(self) -> List[Dict]:
        """List all projects"""
        projects = []
        for path in PROJECTS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                projects.append(
                    {
                        "project_id": data["project_id"],
                        "name": data["name"],
                        "status": data["status"],
                        "stage": data["current_stage"],
                        "created": data["created_at"],
                        "society": data.get("society", {}).get("name", ""),
                    }
                )
            except:
                pass
        return sorted(projects, key=lambda x: x.get("created", ""), reverse=True)

    def get_project_progress(self, project: Project) -> Dict:
        """Get project progress summary"""
        total = len(project.workflow_steps)
        completed = sum(1 for s in project.workflow_steps if s.status == "completed")
        in_progress = sum(
            1 for s in project.workflow_steps if s.status == "in_progress"
        )
        pending = total - completed - in_progress

        return {
            "total_steps": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "progress_pct": int((completed / total) * 100) if total > 0 else 0,
            "available_steps": [s.name for s in self.get_available_steps(project)],
            "current_stage": project.current_stage.value,
            "status": project.status.value,
            "days_elapsed": (datetime.now() - project.created_at).days
            if project.created_at
            else 0,
            "days_remaining": (project.estimated_completion - datetime.now()).days
            if project.estimated_completion
            else 0,
        }


class TenderManager:
    """Manage tender process"""

    def __init__(self, workflow_engine: PMCWorkflowEngine):
        self.workflow = workflow_engine

    def create_tender(self, project: Project, tender_type: str = "e_tender") -> Tender:
        """Create a new tender"""
        tender = Tender(
            tender_id=f"TENDER_{project.project_id}_{len(project.tenders) + 1}",
            type=tender_type,
            publication_date=datetime.now(),
            submission_deadline=datetime.now() + timedelta(days=30),
            technical_bid_opening=datetime.now() + timedelta(days=35),
            financial_bid_opening=datetime.now() + timedelta(days=40),
            status="draft",
        )

        project.tenders.append(tender)
        self.workflow.save_project(project)

        return tender

    def publish_tender(self, tender: Tender, project: Project) -> Project:
        """Publish tender"""
        tender.status = "published"
        tender.publication_date = datetime.now()
        self.workflow.save_project(project)

        self.workflow.update_step_status(
            project, "step_4", "completed", f"Tender {tender.tender_id} published"
        )
        return project

    def evaluate_bids(self, tender: Tender, bids: List[Dict], project: Project) -> Dict:
        """Evaluate submitted bids"""
        tender.status = "evaluation"

        # Create comparison matrix
        comparison = {
            "bids": bids,
            "criteria": ["FSI Offered", "Revenue Share", "Timeline", "Experience"],
            "weights": [0.3, 0.3, 0.2, 0.2],
        }

        # Score bids
        for bid in bids:
            scores = []
            for criterion in comparison["criteria"]:
                score = float(bid.get(criterion.lower().replace(" ", "_"), 0))
                scores.append(score)
            bid["total_score"] = sum(
                s * w for s, w in zip(scores, comparison["weights"])
            )

        # Sort by score
        comparison["bids"] = sorted(bids, key=lambda x: x["total_score"], reverse=True)
        comparison["recommended"] = (
            comparison["bids"][0] if comparison["bids"] else None
        )

        tender.status = "evaluated"
        self.workflow.save_project(project)

        self.workflow.update_step_status(
            project,
            "step_5",
            "completed",
            f"Recommended: {comparison['recommended']['name']}",
        )

        return comparison


# CLI Commands
def cmd_create_project(args):
    """Create new project"""
    from .property_card_workflow import PropertyCard

    engine = PMCWorkflowEngine()

    # Create society
    society = Society(
        name=args.society_name,
        registration_no=args.society_reg,
        address=args.address,
        total_members=args.members,
        voting_quorum=int(args.members * 0.7),
    )

    # Create plot details
    plot = PlotDetails(
        survey_no=args.survey_no,
        area_sq_m=args.area,
        area_sq_ft=args.area * 10.764,
        road_width_m=args.road_width,
        zone_type=args.zone,
    )

    # Create project
    project = engine.create_project(args.project_name, society, plot, args.pmc)

    logger.info(f"✓ Project created: {project.project_id}")
    logger.info(f"  Name: {project.name}")
    logger.info(f"  Society: {society.name}")
    logger.info(f"  Survey No: {plot.survey_no}")
    logger.info(f"  Plot Area: {plot.area_sq_m} sq.m")
    logger.info(f"  Workflow Steps: {len(project.workflow_steps)}")
    logger.info(f"\nNext: python3 pmc_workflow.py progress {project.project_id}")


def cmd_generate_report(args):
    """Generate feasibility or DDR report"""
    engine = PMCWorkflowEngine()
    project = engine.load_project(args.project_id)

    doc = engine.generate_document(project, args.doc_type)
    logger.info(f"✓ Document generated: {doc.title}")
    logger.info(f"  File: {doc.file_path}")
    logger.info(f"  Doc ID: {doc.doc_id}")


def cmd_progress(args):
    """Show project progress"""
    engine = PMCWorkflowEngine()
    project = engine.load_project(args.project_id)

    progress = engine.get_project_progress(project)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"PROJECT: {project.name} ({project.project_id})")
    logger.info(f"{'=' * 60}")
    logger.info(f"Status: {project.status.value.upper()}")
    logger.info(f"Stage: {project.current_stage.value.upper().replace('_', ' ')}")
    logger.info(f"\nProgress: {progress['progress_pct']}%")
    logger.info(f"  Completed: {progress['completed']}/{progress['total_steps']}")
    logger.info(f"  In Progress: {progress['in_progress']}")
    logger.info(f"  Pending: {progress['pending']}")

    if progress["days_remaining"] > 0:
        logger.info(
            f"\nTimeline: {progress['days_elapsed']} days elapsed, ~{progress['days_remaining']} days remaining"
        )

    logger.info(f"\nAvailable Actions:")
    for step_name in progress["available_steps"]:
        logger.info(f"  → {step_name}")

    logger.info(f"\nDocuments ({len(project.documents)}):")
    for doc in project.documents:
        logger.info(f"  - {doc.doc_type}: {doc.status}")


def cmd_list_projects(args):
    """List all projects"""
    engine = PMCWorkflowEngine()
    projects = engine.list_projects()

    logger.info(f"\n{'ID':<12} {'Name':<30} {'Status':<15} {'Stage':<20} {'Society'}")
    logger.info("-" * 100)
    for p in projects:
        logger.info(
            f"{p['project_id']:<12} {p['name'][:28]:<30} {p['status']:<15} "
            f"{p['stage']:<20} {p.get('society', '')[:20]}"
        )


def cmd_init_deemed_conveyance(args):
    """Initiate deemed conveyance"""
    engine = PMCWorkflowEngine()
    project = engine.load_project(args.project_id)

    project = engine.initiate_deemed_conveyance(
        project,
        developer_name=args.developer,
        developer_address=args.developer_address,
        lawyer_name=args.lawyer,
    )

    logger.info(f"✓ Deemed Conveyance initiated for project {project.project_id}")
    logger.info(f"  Lawyer: {args.lawyer}")
    logger.info(f"  Developer: {args.developer}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PMC Workflow System")
    subparsers = parser.add_subparsers(dest="cmd")

    # Create project
    create_parser = subparsers.add_parser("create", help="Create new project")
    create_parser.add_argument("project_name", help="Project name")
    create_parser.add_argument("--society-name", required=True, help="Society name")
    create_parser.add_argument(
        "--society-reg", required=True, help="Society registration no"
    )
    create_parser.add_argument("--survey-no", required=True, help="Survey number")
    create_parser.add_argument(
        "--area", type=float, required=True, help="Plot area in sq.m"
    )
    create_parser.add_argument(
        "--road-width", type=float, default=9, help="Road width in meters"
    )
    create_parser.add_argument("--zone", default="Residential", help="Zone type")
    create_parser.add_argument(
        "--members", type=int, default=50, help="Total society members"
    )
    create_parser.add_argument("--address", default="", help="Society address")
    create_parser.add_argument("--pmc", default="Default PMC", help="PMC name")

    # Generate report
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("project_id", help="Project ID")
    report_parser.add_argument(
        "--type",
        default="feasibility",
        choices=[
            "feasibility",
            "ddr_report",
            "provisional_agreement",
            "da",
            "poa",
            "deemed_conveyance_notice",
        ],
        help="Report type",
    )

    # Progress
    progress_parser = subparsers.add_parser("progress", help="Show project progress")
    progress_parser.add_argument("project_id", help="Project ID")

    # List projects
    subparsers.add_parser("list", help="List all projects")

    # Deemed conveyance
    dc_parser = subparsers.add_parser(
        "deemed-conveyance", help="Initiate deemed conveyance"
    )
    dc_parser.add_argument("project_id", help="Project ID")
    dc_parser.add_argument("--developer", required=True, help="Developer name")
    dc_parser.add_argument(
        "--developer-address", required=True, help="Developer address"
    )
    dc_parser.add_argument("--lawyer", required=True, help="Lawyer name")

    args = parser.parse_args()

    if args.cmd == "create":
        cmd_create_project(args)
    elif args.cmd == "report":
        cmd_generate_report(args)
    elif args.cmd == "progress":
        cmd_progress(args)
    elif args.cmd == "list":
        cmd_list_projects(args)
    elif args.cmd == "deemed-conveyance":
        cmd_init_deemed_conveyance(args)
    else:
        parser.print_help()
