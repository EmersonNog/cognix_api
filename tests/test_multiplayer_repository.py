import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.services.multiplayer import repository
from app.services.multiplayer.data import tables as multiplayer_tables


class MultiplayerRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine('sqlite:///:memory:')
        self.metadata = MetaData()
        self.rooms = Table(
            'test_multiplayer_rooms',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('pin', String(6), nullable=False),
            Column('host_user_id', Integer, nullable=False),
            Column('host_firebase_uid', String(255), nullable=False),
            Column('status', String(40), nullable=False),
            Column('max_participants', Integer, nullable=False, default=10),
            Column('question_ids', repository._rooms_table().c.question_ids.type, nullable=True),
            Column('current_question_index', Integer, nullable=False, default=0),
            Column('round_duration_seconds', Integer, nullable=False, default=60),
            Column('started_at', DateTime(timezone=True), nullable=True),
            Column('round_started_at', DateTime(timezone=True), nullable=True),
            Column('finished_at', DateTime(timezone=True), nullable=True),
            Column('created_at', DateTime(timezone=True), nullable=True),
            Column('updated_at', DateTime(timezone=True), nullable=True),
        )
        self.participants = Table(
            'test_multiplayer_participants',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('room_id', Integer, nullable=False),
            Column('user_id', Integer, nullable=False),
            Column('firebase_uid', String(255), nullable=False),
            Column('display_name', String(255), nullable=True),
            Column('role', String(40), nullable=False),
            Column('status', String(40), nullable=False),
            Column('score', Integer, nullable=False, default=0),
            Column('correct_answers', Integer, nullable=False, default=0),
            Column('answered_current_question', Boolean, nullable=False, default=False),
            Column('current_question_id', Integer, nullable=True),
            Column('selected_letter', String(2), nullable=True),
            Column('last_answered_at', DateTime(timezone=True), nullable=True),
            Column('joined_at', DateTime(timezone=True), nullable=True),
            Column('removed_at', DateTime(timezone=True), nullable=True),
            Column('created_at', DateTime(timezone=True), nullable=True),
            Column('updated_at', DateTime(timezone=True), nullable=True),
        )
        self.questions = Table(
            'test_questions',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('gabarito', String(2), nullable=True),
        )
        self.metadata.create_all(self.engine)

        session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db: Session = session_factory()

        self._original_rooms_table = multiplayer_tables.rooms_table
        self._original_participants_table = multiplayer_tables.participants_table
        self._original_questions_table = multiplayer_tables.questions_table
        multiplayer_tables.rooms_table = lambda: self.rooms
        multiplayer_tables.participants_table = lambda: self.participants
        multiplayer_tables.questions_table = lambda: self.questions

    def tearDown(self) -> None:
        multiplayer_tables.rooms_table = self._original_rooms_table
        multiplayer_tables.participants_table = self._original_participants_table
        multiplayer_tables.questions_table = self._original_questions_table
        self.db.close()
        self.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _seed_room(
        self,
        *,
        room_id: int = 1,
        status: str = repository.ROOM_STATUS_WAITING,
        question_ids=None,
        current_question_index: int = 0,
        round_duration_seconds: int = 60,
    ) -> None:
        now = datetime.now(UTC)
        self.db.execute(
            self.rooms.insert().values(
                id=room_id,
                pin='123456',
                host_user_id=1,
                host_firebase_uid='host-uid',
                status=status,
                max_participants=10,
                question_ids=question_ids,
                current_question_index=current_question_index,
                round_duration_seconds=round_duration_seconds,
                started_at=now,
                round_started_at=now,
                finished_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        self.db.commit()

    def _seed_participant(
        self,
        *,
        participant_id: int,
        room_id: int,
        user_id: int,
        firebase_uid: str,
        display_name: str,
        role: str,
        status: str = repository.PARTICIPANT_STATUS_JOINED,
        score: int = 0,
        correct_answers: int = 0,
        answered_current_question: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        self.db.execute(
            self.participants.insert().values(
                id=participant_id,
                room_id=room_id,
                user_id=user_id,
                firebase_uid=firebase_uid,
                display_name=display_name,
                role=role,
                status=status,
                score=score,
                correct_answers=correct_answers,
                answered_current_question=answered_current_question,
                current_question_id=None,
                selected_letter=None,
                last_answered_at=None,
                joined_at=now,
                removed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        self.db.commit()

    def _seed_question(self, question_id: int, answer_key: str) -> None:
        self.db.execute(
            self.questions.insert().values(id=question_id, gabarito=answer_key)
        )
        self.db.commit()

    def test_join_room_allows_existing_joined_player_to_reconnect_in_progress(self) -> None:
        self._seed_room(status=repository.ROOM_STATUS_IN_PROGRESS, question_ids=[10, 11])
        self._seed_participant(
            participant_id=1,
            room_id=1,
            user_id=1,
            firebase_uid='host-uid',
            display_name='Host',
            role=repository.ROLE_HOST,
        )
        self._seed_participant(
            participant_id=2,
            room_id=1,
            user_id=2,
            firebase_uid='player-uid',
            display_name='Player',
            role=repository.ROLE_PLAYER,
        )

        room = repository.join_room(
            self.db,
            pin='123456',
            user_id=2,
            firebase_uid='player-uid',
            display_name='Player',
        )

        self.assertEqual(room['status'], repository.ROOM_STATUS_IN_PROGRESS)
        self.assertEqual(room['participant_count'], 2)

    def test_leave_room_advances_round_when_last_pending_player_leaves(self) -> None:
        self._seed_room(
            status=repository.ROOM_STATUS_IN_PROGRESS,
            question_ids=[10, 11],
            current_question_index=0,
        )
        self._seed_participant(
            participant_id=1,
            room_id=1,
            user_id=1,
            firebase_uid='host-uid',
            display_name='Host',
            role=repository.ROLE_HOST,
            answered_current_question=True,
            score=100,
            correct_answers=1,
        )
        self._seed_participant(
            participant_id=2,
            room_id=1,
            user_id=2,
            firebase_uid='player-a',
            display_name='Player A',
            role=repository.ROLE_PLAYER,
            answered_current_question=True,
        )
        self._seed_participant(
            participant_id=3,
            room_id=1,
            user_id=3,
            firebase_uid='player-b',
            display_name='Player B',
            role=repository.ROLE_PLAYER,
            answered_current_question=False,
        )

        room = repository.leave_room(self.db, room_id=1, user_id=3)

        self.assertEqual(room['current_question_index'], 1)
        self.assertEqual(room['status'], repository.ROOM_STATUS_IN_PROGRESS)
        self.assertTrue(
            all(
                participant['answered_current_question'] is False
                for participant in room['participants']
            )
        )

    def test_serialize_room_includes_server_time_and_official_ranking(self) -> None:
        self._seed_room(status=repository.ROOM_STATUS_FINISHED, question_ids=[10, 11])
        self._seed_participant(
            participant_id=1,
            room_id=1,
            user_id=1,
            firebase_uid='host-uid',
            display_name='Beta',
            role=repository.ROLE_HOST,
            score=100,
            correct_answers=1,
        )
        self._seed_participant(
            participant_id=2,
            room_id=1,
            user_id=2,
            firebase_uid='player-a',
            display_name='Alfa',
            role=repository.ROLE_PLAYER,
            score=300,
            correct_answers=3,
        )
        self._seed_participant(
            participant_id=3,
            room_id=1,
            user_id=3,
            firebase_uid='player-b',
            display_name='Gama',
            role=repository.ROLE_PLAYER,
            score=300,
            correct_answers=2,
        )

        room = repository.serialize_room(self.db, 1)

        self.assertIn('server_time', room)
        self.assertEqual(
            [participant['display_name'] for participant in room['ranking']],
            ['Alfa', 'Gama', 'Beta'],
        )

    def test_host_leave_returns_closed_snapshot_with_reason(self) -> None:
        self._seed_room(
            status=repository.ROOM_STATUS_IN_PROGRESS,
            question_ids=[10, 11],
            current_question_index=0,
        )
        self._seed_participant(
            participant_id=1,
            room_id=1,
            user_id=1,
            firebase_uid='host-uid',
            display_name='Host',
            role=repository.ROLE_HOST,
            score=200,
            correct_answers=2,
        )
        self._seed_participant(
            participant_id=2,
            room_id=1,
            user_id=2,
            firebase_uid='player-a',
            display_name='Player',
            role=repository.ROLE_PLAYER,
            score=100,
            correct_answers=1,
        )

        payload = repository.leave_room(self.db, room_id=1, user_id=1)

        self.assertEqual(payload['status'], 'closed')
        self.assertEqual(payload['reason'], repository.ROOM_CLOSED_REASON_HOST_LEFT)
        self.assertEqual(payload['room']['status'], 'closed')
        self.assertEqual(payload['room']['ranking'][0]['display_name'], 'Host')

    def test_submit_answer_updates_score_and_finishes_match_on_last_question(self) -> None:
        started_at = datetime.now(UTC) - timedelta(seconds=5)
        self.db.execute(
            self.rooms.insert().values(
                id=1,
                pin='123456',
                host_user_id=1,
                host_firebase_uid='host-uid',
                status=repository.ROOM_STATUS_IN_PROGRESS,
                max_participants=10,
                question_ids=[10],
                current_question_index=0,
                round_duration_seconds=60,
                started_at=started_at,
                round_started_at=started_at,
                finished_at=None,
                created_at=started_at,
                updated_at=started_at,
            )
        )
        self.db.commit()
        self._seed_participant(
            participant_id=1,
            room_id=1,
            user_id=1,
            firebase_uid='host-uid',
            display_name='Host',
            role=repository.ROLE_HOST,
        )
        self._seed_participant(
            participant_id=2,
            room_id=1,
            user_id=2,
            firebase_uid='player-a',
            display_name='Player',
            role=repository.ROLE_PLAYER,
        )
        self._seed_question(10, 'A')

        first = repository.submit_answer(
            self.db,
            room_id=1,
            user_id=1,
            question_id=10,
            selected_letter='A',
        )
        second = repository.submit_answer(
            self.db,
            room_id=1,
            user_id=2,
            question_id=10,
            selected_letter='B',
        )

        self.assertEqual(first['score'], 100)
        self.assertEqual(second['room']['status'], repository.ROOM_STATUS_FINISHED)
        self.assertEqual(second['room']['ranking'][0]['display_name'], 'Host')


if __name__ == '__main__':
    unittest.main()
