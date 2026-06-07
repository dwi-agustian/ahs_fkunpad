from django.db import models
from django.utils import timezone

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Family(TimeStampedModel):
    external_id = models.CharField(max_length=100, blank=True, null=True, help_text="REDCap: family_id")
    source = models.CharField(max_length=50, blank=True, null=True, help_text="Source system (e.g., 'redcap')")
    name = models.CharField(max_length=200, blank=True, null=True, help_text="REDCap: family_name")
    contact_phone = models.CharField(max_length=30, blank=True, null=True, help_text="REDCap: family_contact_phone")
    contact_email = models.EmailField(blank=True, null=True, help_text="REDCap: family_contact_email")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["external_id"]), models.Index(fields=["name"])]

    def __str__(self):
        return self.name or f"Family {self.pk}"

class Patient(TimeStampedModel):
    SEX_MALE = 'M'
    SEX_FEMALE = 'F'
    SEX_OTHER = 'O'
    SEX_UNKNOWN = 'U'
    SEX_CHOICES = [
        (SEX_MALE, 'Male'),
        (SEX_FEMALE, 'Female'),
        (SEX_OTHER, 'Other'),
        (SEX_UNKNOWN, 'Unknown'),
    ]

    external_id = models.CharField(max_length=100, unique=True, help_text="REDCap: patient_id")
    source = models.CharField(max_length=50, blank=True, null=True, help_text="Source system (e.g., 'redcap')")
    source_record_id = models.CharField(max_length=100, blank=True, null=True, help_text="Original REDCap record id")
    redcap_payload = models.JSONField(blank=True, null=True, help_text="Raw REDCap record JSON")

    first_name = models.CharField(max_length=150, blank=True, null=True, help_text="REDCap: first_name")
    last_name = models.CharField(max_length=150, blank=True, null=True, help_text="REDCap: last_name")
    birth_date = models.DateField(blank=True, null=True, help_text="REDCap: birth_date")
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, default=SEX_UNKNOWN, help_text="REDCap: sex")

    national_id = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="REDCap: national_id")
    diagnosis = models.TextField(blank=True, null=True, help_text="REDCap: primary_diagnosis")

    family = models.ForeignKey(Family, on_delete=models.SET_NULL, blank=True, null=True, related_name="patients", help_text="REDCap: family_id")

    email = models.EmailField(blank=True, null=True, help_text="REDCap: email")
    phone = models.CharField(max_length=30, blank=True, null=True, help_text="REDCap: phone")

    last_synced_at = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["national_id"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["external_id"], name="uq_patient_external_id")
        ]

    def __str__(self):
        return f"{self.last_name or ''}, {self.first_name or ''} ({self.external_id})"

    @property
    def age_at(self, ref_date=None):
        """
        Return age in years at ref_date (datetime.date or datetime.datetime).
        If ref_date is None, use today().
        Returns None if birth_date is not set.
        """
        if not self.birth_date:
            return None
        if ref_date is None:
            ref_date = timezone.localdate()
        # if a datetime is passed, convert to date
        if hasattr(ref_date, "date"):
            ref_date = ref_date.date()
        years = ref_date.year - self.birth_date.year
        if (ref_date.month, ref_date.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    def mark_synced(self, payload=None):
        self.last_synced_at = timezone.now()
        if payload is not None:
            self.redcap_payload = payload
        self.save(update_fields=["last_synced_at", "redcap_payload"] if payload is not None else ["last_synced_at"])

class Visit(TimeStampedModel):
    # Provenance / external ids (populated from REDCap)
    external_id = models.CharField(
        max_length=100,
        unique=False,
        blank=True,
        null=True,
        help_text="Canonical external id (e.g., REDCap visit_id or rotation_id)"
    )
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Source system (e.g., 'redcap')"
    )
    source_record_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Original REDCap record id (if different)"
    )
    redcap_payload = models.JSONField(
        blank=True,
        null=True,
        help_text="Raw REDCap record JSON for traceability"
    )

    # Relationships (patient and facility)
    patient = models.ForeignKey(
    	Patient, on_delete=models.CASCADE, related_name="visits", 
    	help_text="Patient FK (mapped from REDCap: patient_id)"
    )
    facility = models.ForeignKey(
    	Facility, on_delete=models.PROTECT, related_name="visits", 
    	help_text="Facility FK (mapped from REDCap: site_id)"
    )

    # Visit timing and status (from REDCap)
    visit_start = models.DateTimeField(blank=True, null=True, help_text="REDCap: visit_start or rotation_start")
    visit_end = models.DateTimeField(blank=True, null=True, help_text="REDCap: visit_end or rotation_end")
    visit_status = models.CharField(max_length=50, blank=True, null=True, help_text="REDCap: rotation_status (planned/ongoing/completed/cancelled)")
    academic_year = models.CharField(max_length=32, blank=True, null=True, help_text="REDCap: academic_year")
    role = models.CharField(max_length=50, blank=True, null=True, help_text="Role of provider on visit (if present)")

    # Sync metadata
    last_synced_at = models.DateTimeField(blank=True, null=True, help_text="When this record was last synced from REDCap")

    class Meta:
        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["source", "source_record_id"]),
            models.Index(fields=["visit_start"]),
        ]

    def __str__(self):
        return f"Visit {self.pk} - patient:{self.patient_id} facility:{self.facility_id} start:{self.visit_start}"

    @property
    def age_at_visit(self):
        """
        Patient age in years at the visit_start datetime.
        """
        if not self.visit_start:
            return None
        return self.patient.age_at(self.visit_start)

    def mark_synced(self, payload=None):
        self.last_synced_at = timezone.now()
        if payload is not None:
            self.redcap_payload = payload
        self.save(update_fields=["last_synced_at", "redcap_payload"] if payload is not None else ["last_synced_at"])

class Facility(TimeStampedModel):
    """
    Canonical facility record. Clinic and Hospital are subtypes linked by OneToOne.
    """
    external_id = models.CharField(max_length=100, blank=True, null=True, help_text="REDCap facility id (if present)")
    source = models.CharField(max_length=50, blank=True, null=True, help_text="Source system (e.g., 'redcap')")
    source_record_id = models.CharField(max_length=100, blank=True, null=True, help_text="Original record id in source")
    redcap_payload = models.JSONField(blank=True, null=True, help_text="Raw REDCap record JSON")

    name = models.CharField(max_length=255, help_text="Canonical facility name")
    enrolled = models.BooleanField(default=False, help_text="Enrolled in AHS network")
    enrollment_date = models.DateField(blank=True, null=True)
    network_id = models.CharField(max_length=100, blank=True, null=True)

    address = models.TextField(blank=True, null=True)
    contact_name = models.CharField(max_length=150, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=50, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "external_id"]),
            models.Index(fields=["name"]),
            models.Index(fields=["enrolled"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="uq_facility_source_external"),
        ]

    def __str__(self):
        return self.name


class Clinic(TimeStampedModel):
    """
    Clinic-specific data. One-to-one relation to Facility.
    """
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE, related_name="clinic")
    clinic_specific_field = models.CharField(max_length=200, blank=True, null=True, help_text="Example clinic-specific attribute")
    # provenance duplicates optional for easier sync
    external_id = models.CharField(max_length=100, blank=True, null=True, help_text="REDCap clinic_id")
    redcap_payload = models.JSONField(blank=True, null=True, help_text="Raw REDCap clinic record")
    last_synced_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Clinic: {self.facility.name}"


class Hospital(TimeStampedModel):
    """
    Hospital-specific data. One-to-one relation to Facility.
    """
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE, related_name="hospital")
    hospital_specific_field = models.CharField(max_length=200, blank=True, null=True, help_text="Example hospital-specific attribute")
    # provenance duplicates optional for easier sync
    external_id = models.CharField(max_length=100, blank=True, null=True, help_text="REDCap hospital_id")
    redcap_payload = models.JSONField(blank=True, null=True, help_text="Raw REDCap hospital record")
    last_synced_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Hospital: {self.facility.name}"


class Organization(TimeStampedModel):
    CATEGORY_ACADEMIC = 'academic'
    CATEGORY_HEALTH = 'healthcare'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_ACADEMIC, 'Academic'),
        (CATEGORY_HEALTH, 'Health Care'),
        (CATEGORY_OTHER, 'Other'),
    ]
# Subtypes cover university vs non-university and healthcare levels
    SUB_UNIVERSITY = 'university'
    SUB_NON_UNIV = 'non_university'
    SUB_PRIMARY_PRIVATE = 'primary_private'
    SUB_PRIMARY_GOV = 'primary_government'
    SUB_REFERRAL_PRIVATE = 'referral_private'
    SUB_REFERRAL_GOV = 'referral_government'
    SUB_CHOICES = [
        (SUB_UNIVERSITY, 'University'),
        (SUB_NON_UNIV, 'Non-University Academic'),
        (SUB_PRIMARY_PRIVATE, 'Primary Care - Private Clinic'),
        (SUB_PRIMARY_GOV, 'Primary Care - Government Clinic'),
        (SUB_REFERRAL_PRIVATE, 'Referral Care - Private Hospital'),
        (SUB_REFERRAL_GOV, 'Referral Care - Government Hospital'),
        ]
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    subtype = models.CharField(max_length=32, choices=SUB_CHOICES, blank=True)
    code = models.CharField(max_length=64, blank=True, null=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return self.name

class FacultyUnit(TimeStampedModel):
    organization = models.ForeignKey(Organization, related_name='faculty_units', 	 on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True)
    dean = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.name} — {self.organization.name}"

class Department(TimeStampedModel):
    faculty = models.ForeignKey(FacultyUnit, related_name='departments', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    head = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.name} — {self.faculty.name}"
      
class StudyProgram(TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True)
    level = models.CharField(max_length=50, blank=True)  # e.g., Undergraduate, Masters, PhD
    
    def __str__(self):
        return self.name
      
class Person(TimeStampedModel):
    ROLE_CHOICES = [
        ('faculty', 'Faculty Member'),
        ('student', 'Student'),
        ('admin', 'Administration Staff'),
        ('physician', 'Practicing Physician'),
        ('nurse', 'Practicing Nurse'),
        ('midwife', 'Practicing Midwife'),
        ('dentist', 'Practicing Dentist'),
        ('pharmacist', 'Practicing Pharmacist'),
        ('psychologist', 'Practicing Psychologist'),
        ('research_assistant', 'Research Assistant'),
        ('teaching_assistant', 'Teaching Assistant'),
        ('patient', 'Patient'),
        ('family', 'Family'),
        ('community', 'Community'),
    ]
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    person_id = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    organization = models.ForeignKey(Organization, related_name='people', on_delete=models.SET_NULL, null=True, blank=True)
    faculty_unit = models.ForeignKey(FacultyUnit, related_name='people', on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey(Department, related_name='people', on_delete=models.SET_NULL, null=True, blank=True)
    study_program = models.ForeignKey(StudyProgram, related_name='people', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=['role']), models.Index(fields=['person_id'])]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.person_id})"

class MedicalSpecialization(models.Model):
    """
    Use to represent general/specialist/sub-specialist categories for physicians/dentists.
    """
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='subspecialties', 	on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class ClinicianProfile(TimeStampedModel):
    """
    Extra clinical fields linked to Person where role is physician/nurse/dentist/etc.
    """
    person = models.OneToOneField(Person, related_name='clinician_profile', on_delete=models.CASCADE)
    license_number = models.CharField(max_length=128, blank=True)
    profession = models.CharField(max_length=64, blank=True)  # Physician, Nurse, Dentist, Pharmacist, etc.
    specialization = models.ForeignKey(MedicalSpecialization, null=True, blank=True, on_delete=models.SET_NULL)
    is_active_practitioner = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.person} — {self.profession}"


