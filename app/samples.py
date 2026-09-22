"""Built-in demo letters (fictional) used by the UI's one-click buttons and by tests."""

from pydantic import BaseModel


class Sample(BaseModel):
    """A demo input."""

    id: str
    title: str
    text: str


SAMPLES: tuple[Sample, ...] = (
    Sample(
        id="obvious_scam",
        title="Obvious scam: fake TCS offer",
        text=(
            "Dear Candidate,\n"
            "Congratulations!! You are selected for the post of Data Entry Executive in "
            "Tata Consultancy Services without any interview. Your salary will be Rs. 85,000 "
            "per month for work from home.\n"
            "To confirm your seat you must pay a refundable registration fee of Rs. 4,999 "
            "via UPI to tcshr.recruit@ybl within 24 hours, failing which your offer will be "
            "cancelled.\n"
            "Kindly send your Aadhaar card, PAN card and bank account details on WhatsApp.\n"
            "Complete joining formality at http://tcs-careers.xyz/joining\n"
            "Regards,\nHR Team\nhr.tcs.recruitment@gmail.com"
        ),
    ),
    Sample(
        id="subtle_scam",
        title="Subtle scam: laptop deposit",
        text=(
            "Dear Priya,\n"
            "Further to your telephonic discussion with our hiring team, we are pleased to "
            "offer you the position of Junior Business Analyst at Nexora Analytics Pvt. Ltd. "
            "with an annual CTC of INR 4,20,000.\n"
            "As this is a remote role, the company will ship you a configured laptop. Please "
            "transfer a refundable security deposit of INR 7,500 to the account below; it will "
            "be returned with your first salary.\n"
            "Kindly share your bank account details and a cancelled cheque for payroll setup. "
            "Please confirm by Friday to secure your joining date.\n"
            "Onboarding portal: https://nexora-hr.co/onboarding\n"
            "Warm regards,\nTalent Acquisition, Nexora Analytics\nonboarding@nexora-hr.co"
        ),
    ),
    Sample(
        id="rental_scam",
        title="Rental deposit trap",
        text=(
            "Hello, the 2BHK flat in Koramangala is still available at Rs. 18,000/month. "
            "I am currently working abroad so I cannot show the flat in person. Many people "
            "are interested, limited slots, so pay the token advance of Rs. 10,000 through "
            "PhonePe to rentowner.blr@ybl today itself and I will courier the keys. "
            "The deposit is fully refundable. Photos: https://bit.ly/flat-photos-blr\n"
            "Contact: owner.flats.blr@yahoo.com"
        ),
    ),
    Sample(
        id="legitimate",
        title="Legitimate offer",
        text=(
            "Dear Rahul Sharma,\n"
            "Following your technical and HR interview rounds on 12 August, we are pleased "
            "to offer you the role of Systems Engineer at Infosys Limited, Mysuru, with an "
            "annual compensation of INR 3,60,000 as detailed in Annexure A.\n"
            "Please accept this offer through the candidate portal at "
            "https://www.infosys.com/careers within 7 days.\n"
            "Please carry your original educational certificates and PAN card for "
            "verification on the day of joining. Infosys never charges candidates any fee "
            "at any stage of recruitment.\n"
            "Sincerely,\nTalent Acquisition, Infosys Limited\ncareers@infosys.com"
        ),
    ),
)


def get_sample(sample_id: str) -> Sample:
    """Return a sample by id (raises KeyError if unknown)."""
    for sample in SAMPLES:
        if sample.id == sample_id:
            return sample
    raise KeyError(sample_id)
