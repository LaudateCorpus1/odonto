import datetime
import xml.etree.ElementTree as ET
from django.db import models
from django.utils import timezone
from django.conf import settings
from opal.models import Episode
from odonto.odonto_submissions import dpb_api, logger, serializers
from odonto.odonto_submissions.exceptions import MessageSendingException

# before this date we used transmission id, after this date
# we use episode id.
# transmission id was used because it was easier but in the
# case where we are repeatedly sending down a submission
# given a submission is on a per episode basis it makes more
# sense to use the episode id
SUBMISSION_ID_DATE_CHANGE = datetime.date(2019, 11, 5)


class Transmission(models.Model):
    """
    A transmission is an occassion on which we send a message to an
    upstream system.

    In our current implementation when we send data upstream we make
    one transmission per episode, however this is not mandated by the
    upstream spec.

    This model provides such transmissions with a uniquie ID.
    """
    transmission_id = models.IntegerField(unique=True)

    class Meta:
        ordering = ('-transmission_id',)

    def __str__(self):
        return "<Transmission id={0.id} transmission id={0.transmission_id}>".format(
            self
        )

    @classmethod
    def create(cls):
        instance = cls()
        if not cls.objects.exists():
            instance.transmission_id = 1
        else:
            max_number = cls.objects.aggregate(
                number=models.Max("transmission_id")
            )["number"] + 1
            instance.transmission_id = max_number
        instance.save()
        return instance


class Response(models.Model):
    """
    This requests and stores everything from the dpb api get_responses method
    """

    SUCCESS = "Success"
    FAILED = "Failed"

    STATUS = (
        (SUCCESS, SUCCESS,),
        (FAILED, FAILED,),
    )
    created = models.DateTimeField(default=timezone.now)
    content = models.TextField(default="")
    state = models.CharField(
        default="", choices=STATUS, max_length=256
    )

    def __str__(self):
        return "<Response id={0.id} created={0.created} state={0.state}>".format(
            self
        )

    @classmethod
    def get(cls):
        batch_response = cls()
        response = None
        try:
            response = dpb_api.get_responses()
            batch_response.content = response
            batch_response.state = cls.SUCCESS
            batch_response.save()
            logger.info("Successfully requested the batch responses")
            return batch_response
        except Exception as e:
            batch_response.state = cls.FAILED
            batch_response.save()
            logger.error(f"Batch response failed with {e}")
            raise

    def get_root(self):
        return ET.fromstring(self.content)

    def get_all_submissions(self):
        """
        All submissions mentioned in this batch response
        """
        root = self.get_root()
        transmission_ids = [i.attrib["seq"] for i in root.iter('contrl')]
        if not transmission_ids:
            return Submission.objects.none()
        return Submission.objects.filter(
            transmission__transmission_id__in=transmission_ids
        )

    def get_rejected_submissions(self):
        """
        Returns a dictionary of failed submissions to error message

        Things are complicated because the id used is the submission_id
        which is episode_id after 10/10/2019 but transmission_id before hand
        """
        submission_id_to_reason = {}
        result = {}
        root = self.get_root()

        for rsp in root.iter('rsp'):
            submission_id = int(rsp.attrib["clrn"])
            submission_id_to_reason[submission_id] = ", ".join(
                [i.text.strip() for i in rsp.findall("mstxt")]
            )

        submissions = self.get_all_submissions()

        for submission in submissions:
            submission_id = submission.get_submission_id()
            # if the submission id isn't in the reponse
            # then its been successful
            if submission_id not in submission_id_to_reason:
                continue
            result[submission] = submission_id_to_reason[submission_id]

        return result

    def get_successfull_submissions(self):
        """
        Returns all successful submissions in this response
        """
        rejected_submissions = self.get_rejected_submissions()
        return self.get_all_submissions().exclude(
            id__in=[i.id for i in rejected_submissions.keys()]
        )

    def update_submissions(self):
        """
        Updates the state of all submissions mentioned in this response
        """
        successful_submissions = self.get_successfull_submissions()
        successful_submissions.update(state=Submission.SUCCESS)
        self.submission_set.add(*successful_submissions)
        rejected_submissions_to_reasons = self.get_rejected_submissions()
        rejected_submissions = Submission.objects.filter(
            id__in=[i.id for i in rejected_submissions_to_reasons.keys()]
        )
        for rejected_submission in rejected_submissions:
            rejected_submission.rejection = rejected_submissions_to_reasons[
                rejected_submission
            ]
            rejected_submission.state = Submission.REJECTED_BY_COMPASS
            rejected_submission.save()

        self.submission_set.add(*rejected_submissions)


class EpisodesBeingInvestigated(models.Model):
    """
    If an episode is being investigated.

    Do not flag it as a warning in the error email
    """
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE
    )
    created = models.DateTimeField(default=timezone.now)


class Submission(models.Model):
    # Message is sent but we are waiting on a response message
    SENT = "Sent"

    # Message is sent and we've received a successful response from Compass
    SUCCESS = "Success"

    # We've attempted to send the message but the POST request failed
    FAILED_TO_SEND = "Failed to send"

    # Message has been sent, a response collected, it was rejected by Compass
    REJECTED_BY_COMPASS = "Rejected by compass"

    # A duplicate paper claim was also submitted
    MANUALLY_PROCESSED = "Manually Processed"

    STATUS = (
        (SENT, SENT,),
        (SUCCESS, SUCCESS,),
        (FAILED_TO_SEND, FAILED_TO_SEND,),
        (REJECTED_BY_COMPASS, REJECTED_BY_COMPASS,),
        (MANUALLY_PROCESSED, MANUALLY_PROCESSED,),
    )

    raw_xml = models.TextField()
    created = models.DateTimeField(default=timezone.now)
    submission_count = models.IntegerField(default=1)
    state = models.CharField(
        default="", choices=STATUS, max_length=256
    )

    # The response tha we receive immediately after we send it
    # NOT the one from the batch process
    request_response = models.TextField(blank=True, default="")

    rejection = models.TextField(blank=True, default="")

    transmission = models.ForeignKey(
        Transmission, blank=True, null=True, on_delete=models.SET_NULL
    )
    episode = models.ForeignKey(
        Episode,
        on_delete=models.CASCADE
    )
    response = models.ForeignKey(
        "Response",
        null=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ('-submission_count',)
        get_latest_by = 'submission_count'
        unique_together = (
            ('episode', 'submission_count'),
        )

    def __str__(self):
        return "<Submission pk={0.pk} raw_xml={0.raw_xml!r} >".format(self)


    @classmethod
    def create(cls, episode):
        latest_submission = episode.submission_set.order_by(
            "-submission_count"
        ).first()

        transmission = Transmission.create()

        if latest_submission is None:
            submission_count = 1
            submission_id = episode.id
        else:
            submission_count = latest_submission.submission_count + 1
            submission_id = latest_submission.get_submission_id()

        xml = serializers.translate_episode_to_xml(
            episode,
            submission_id,
            submission_count,
            transmission.transmission_id
        )
        return cls.objects.create(
            raw_xml=xml,
            submission_count=submission_count,
            episode=episode,
            transmission=transmission
        )

    @classmethod
    def has_changed(episode, latest_submission):
        """
        The outer element of the xml tree is an
        Envelope (generated by fp17.envelope.Envelope).
        It includes the current date and time
        and information about origin and destination
        but nothing about the contents of the FP17
        so we strip this off and compare the contents.
        """
        new_xml = serializers.translate_episode_to_xml(
            episode,
            episode.id,
            latest_submission.submission_count,
            latest_submission.transmission_id
        )
        old_xml = latest_submission.raw_xml
        latest_submission.raw_xml
        old_inner_xml = ET.tostring(ET.fromstring(old_xml).getchildren()[0])
        new_inner_xml = ET.tostring(ET.fromstring(new_xml).getchildren()[0])
        if old_inner_xml == new_inner_xml:
            return False
        return True

    @classmethod
    def send(cls, episode, force=False):
        latest_submission = episode.submission_set.order_by(
            "-created"
        ).first()
        if latest_submission and latest_submission.state == cls.SENT:
            ex = "We have a submission with state {} ie awaiting a response \
from compass for submission {} not sending"
            raise MessageSendingException(ex.format(
                cls.SENT, latest_submission.id
            ))

        if latest_submission and latest_submission.state == cls.SUCCESS:
            ex = "We have a submission with state {} ie successfully submitted \
to compass for submission {} not sending"
            raise MessageSendingException(ex.format(
                cls.SUCCESS, latest_submission.id
            ))

        if latest_submission and not force:
            if not cls.has_changed(episode, latest_submission):
                logger.info(
                    " ".join([
                        f'Submission for episode {episode.id}:',
                        'NOT SENDING as the submission has not changed'
                    ])
                )
                return

        new_submission = cls.create(episode)

        try:
            new_submission.request_response = dpb_api.send_message(
                new_submission.raw_xml
            )
            new_submission.state = cls.SENT
            logger.info("Submission for {} has been sent".format(
                episode
            ))
            new_submission.save()
        except Exception:
            new_submission.state = cls.FAILED_TO_SEND
            logger.error("Submission for {} has failed".format(
                episode
            ))
            new_submission.save()
            raise
        return new_submission

    def get_submission_id(self):
        first_submission = self.episode.submission_set.order_by(
            "created"
        ).first()
        if first_submission.created.date() < SUBMISSION_ID_DATE_CHANGE:
            return first_submission.transmission.id
        else:
            return first_submission.episode.id

    def get_rejection_reason(self):
        if not self.STATUS == self.REJECTED_BY_COMPASS:
            raise ValueError(
                "Submission {} has not been rejected".format(self.id)
            )
        return self.response.rejected_submissions()[self.id]
